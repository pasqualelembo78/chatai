import uuid
import time
import hashlib
import hmac
import json
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from werkzeug.security import generate_password_hash, check_password_hash
import os
import threading

import psycopg2.errors

from db import get_conn, put_conn

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 900       # 15 minuti
REFRESH_TOKEN_EXPIRE = 604800   # 7 giorni

_token_blacklist = set()
_blacklist_lock = threading.Lock()

# ─── Inizializzazione tabella utenti ──────────────────────────────
def init_auth_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user',
                google_id TEXT UNIQUE,
                email TEXT DEFAULT '',
                banned_until TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                persistent_token TEXT UNIQUE
            )
        """)
        # Add persistent_token column if missing (migration)
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'persistent_token'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE users ADD COLUMN persistent_token TEXT UNIQUE")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        put_conn(conn)
    ensure_admin_account()


def ensure_admin_account():
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (admin_username,))
        row = cur.fetchone()
        if row:
            try:
                if not row["password_hash"] or not check_password_hash(row["password_hash"], admin_password):
                    cur.execute(
                        "UPDATE users SET password_hash = %s, role = 'admin' WHERE username = %s",
                        (generate_password_hash(admin_password, method="scrypt"), admin_username)
                    )
                    conn.commit()
                    logger.info(f"Admin account '{admin_username}' password/role refreshed")
            except Exception as e:
                logger.warning(f"Admin password refresh failed: {e}")
            return
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(admin_password, method="scrypt")
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, email) VALUES (%s, %s, %s, 'admin', '')",
            (user_id, admin_username, password_hash)
        )
        conn.commit()
        logger.info(f"Default admin account created: {admin_username}")
    finally:
        put_conn(conn)

# ─── JWT helpers ──────────────────────────────────────────────────
def _get_jwt_secret():
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        # Never silently generate a per-process random secret: it would make
        # tokens minted by one worker invalid on another and expire on restart.
        raise RuntimeError(
            "JWT_SECRET non impostato. Imposta JWT_SECRET in .env (chiave esadecimale sicura)."
        )
    return secret

def _base64url_encode(data):
    return data.hex()

def _base64url_decode(s):
    return bytes.fromhex(s)

def _create_jwt(payload):
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    secret = _get_jwt_secret()
    signature = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).hexdigest()
    return f"{header_b64}.{payload_b64}.{signature}"

def _verify_jwt(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature = parts
        secret = _get_jwt_secret()
        expected = hmac.new(secret.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_base64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        with _blacklist_lock:
            if payload.get("jti") in _token_blacklist:
                return None
        return payload
    except Exception:
        return None

def create_tokens(user_id, role="user"):
    now = time.time()
    jti = str(uuid.uuid4())
    access_payload = {
        "user_id": user_id,
        "role": role,
        "jti": jti,
        "exp": now + ACCESS_TOKEN_EXPIRE,
        "iat": now,
    }
    refresh_jti = str(uuid.uuid4())
    refresh_payload = {
        "user_id": user_id,
        "token_type": "refresh",
        "jti": refresh_jti,
        "exp": now + REFRESH_TOKEN_EXPIRE,
        "iat": now,
    }
    access_token = _create_jwt(access_payload)
    refresh_token = _create_jwt(refresh_payload)
    conn = get_conn()
    try:
        cur = conn.cursor()
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.fromtimestamp(now + REFRESH_TOKEN_EXPIRE, tz=timezone.utc)
        cur.execute(
            "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET token_hash=EXCLUDED.token_hash, expires_at=EXCLUDED.expires_at",
            (refresh_jti, user_id, token_hash, expires_at)
        )
        conn.commit()
    finally:
        put_conn(conn)
    return access_token, refresh_token

def revoke_refresh_token(refresh_token):
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
        conn.commit()
    finally:
        put_conn(conn)

# ─── Persistent Token (API Key) ────────────────────────────────
def ensure_persistent_token(user_id: str) -> str:
    """Get or create a persistent API key for the user. Never expires."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT persistent_token FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row and row["persistent_token"]:
            return row["persistent_token"]
        token = "ptk_" + str(uuid.uuid4()).replace("-", "")
        cur.execute("UPDATE users SET persistent_token = %s WHERE id = %s", (token, user_id))
        conn.commit()
        return token
    finally:
        put_conn(conn)

def validate_persistent_token(token: str) -> Optional[str]:
    """Validate persistent token and return user_id. Never expires."""
    if not token or not token.startswith("ptk_"):
        return None
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE persistent_token = %s", (token,))
        row = cur.fetchone()
        if row:
            return row["id"]
        return None
    finally:
        put_conn(conn)

def reauth_from_persistent_token(persistent_token: str):
    """Exchange persistent token for fresh JWT pair. Returns (access_token, refresh_token, user_id) or None."""
    user_id = validate_persistent_token(persistent_token)
    if not user_id:
        return None
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    finally:
        put_conn(conn)
    role = row["role"] if row else "user"
    access_token, refresh_token = create_tokens(user_id, role)
    return access_token, refresh_token, user_id

def socket_authenticate(token):
    if not token:
        return None
    payload = _verify_jwt(token)
    if not payload or payload.get("token_type") == "refresh":
        return None
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT banned_until FROM users WHERE id = %s", (payload["user_id"],))
        row = cur.fetchone()
    finally:
        put_conn(conn)
    if row and row["banned_until"]:
        try:
            ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(str(row["banned_until"]))
            if ban_time > datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    return payload

# ─── FastAPI Dependencies ─────────────────────────────────────────
class AuthUser:
    def __init__(self, user_id: str, role: str = "user"):
        self.user_id = user_id
        self.role = role

def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None

def _check_banned(user_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT banned_until FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    finally:
        put_conn(conn)
    if row and row["banned_until"]:
        try:
            ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(str(row["banned_until"]))
            if ban_time > datetime.now(timezone.utc):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Account sospeso")
        except HTTPException:
            raise
        except Exception:
            pass

async def jwt_required(request: Request) -> AuthUser:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token mancante")
    payload = _verify_jwt(token)
    if not payload:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token non valido o scaduto")
    if payload.get("token_type") == "refresh":
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Refresh token non permesso qui")
    _check_banned(payload["user_id"])
    return AuthUser(user_id=payload["user_id"], role=payload.get("role", "user"))

async def jwt_optional(request: Request) -> Optional[AuthUser]:
    token = _extract_token(request)
    if not token:
        return None
    payload = _verify_jwt(token)
    if not payload or payload.get("token_type") == "refresh":
        return None
    return AuthUser(user_id=payload["user_id"], role=payload.get("role", "user"))

async def admin_required(request: Request) -> AuthUser:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token mancante")
    payload = _verify_jwt(token)
    if not payload:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token non valido o scaduto")
    if payload.get("role") not in ("admin", "moderator"):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Permessi insufficienti")
    _check_banned(payload["user_id"])
    return AuthUser(user_id=payload["user_id"], role=payload.get("role", "user"))

# ─── Pulizia token scaduti ────────────────────────────────────────
def _cleanup_expired_tokens():
    while True:
        time.sleep(3600)
        try:
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM refresh_tokens WHERE expires_at < CURRENT_TIMESTAMP")
                conn.commit()
                logger.info("Pulizia refresh token scaduti completata")
            finally:
                put_conn(conn)
        except Exception as e:
            logger.warning(f"Errore pulizia token: {e}")

# ─── Google Sign-In ──────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

def _verify_google_token(token):
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests
        info = google_id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        if info.get("aud") != GOOGLE_CLIENT_ID:
            return None
        return info
    except Exception as e:
        logger.warning(f"Google token verification failed: {e}")
        return None
