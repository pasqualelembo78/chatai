import uuid
import time
import hashlib
import hmac
import json
import re
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import threading

import psycopg2.errors

from db import get_conn, put_conn

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    strategy="fixed-window",
)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 900       # 15 minuti
REFRESH_TOKEN_EXPIRE = 604800   # 7 giorni

# Blacklist in-memory (fallback se Redis non disponibile)
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
                last_login TIMESTAMP NULL
            )
        """)
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

# ─── JWT helper ──────────────────────────────────────────────────
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

# ─── Decorator JWT ───────────────────────────────────────────────
def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "Token mancante"}), 401
        payload = _verify_jwt(token)
        if not payload:
            return jsonify({"error": "Token non valido o scaduto"}), 401
        if payload.get("token_type") == "refresh":
            return jsonify({"error": "Refresh token non permesso qui"}), 401
        g.user_id = payload["user_id"]
        g.user_role = payload.get("role", "user")
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT banned_until FROM users WHERE id = %s", (g.user_id,))
            row = cur.fetchone()
        finally:
            put_conn(conn)
        if row and row["banned_until"]:
            try:
                ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
                if ban_time > datetime.now(timezone.utc):
                    return jsonify({"error": "Account sospeso"}), 403
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated

def jwt_optional(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if token:
            payload = _verify_jwt(token)
            if payload and payload.get("token_type") != "refresh":
                g.user_id = payload["user_id"]
                g.user_role = payload.get("role", "user")
            else:
                g.user_id = None
                g.user_role = "anonymous"
        else:
            g.user_id = None
            g.user_role = "anonymous"
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "Token mancante"}), 401
        payload = _verify_jwt(token)
        if not payload:
            return jsonify({"error": "Token non valido o scaduto"}), 401
        if payload.get("role") not in ("admin", "moderator"):
            return jsonify({"error": "Permessi insufficienti"}), 403
        g.user_id = payload["user_id"]
        g.user_role = payload.get("role", "user")
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT banned_until FROM users WHERE id = %s", (g.user_id,))
            row = cur.fetchone()
        finally:
            put_conn(conn)
        if row and row["banned_until"]:
            try:
                ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
                if ban_time > datetime.now(timezone.utc):
                    return jsonify({"error": "Account sospeso"}), 403
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated

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
            ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
            if ban_time > datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    return payload

# ─── Google Sign-In ──────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

@auth_bp.route("/auth/google/client-id", methods=["GET"])
def google_client_id():
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google Sign-In non configurato"}), 404
    return jsonify({"client_id": GOOGLE_CLIENT_ID})

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

@auth_bp.route("/auth/google", methods=["POST"])
def google_login():
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google Sign-In non configurato sul server"}), 500

    data = request.get_json(silent=True) or {}
    id_token = data.get("id_token", "")
    referral_code = data.get("referral_code", "").strip()
    if not id_token:
        return jsonify({"error": "id_token richiesto"}), 400

    info = _verify_google_token(id_token)
    if not info:
        return jsonify({"error": "Token Google non valido"}), 401

    google_id = info["sub"]
    email = info.get("email", "")
    name = info.get("name", email.split("@")[0] if email else "Utente")

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role, banned_until, username FROM users WHERE google_id = %s", (google_id,))
        row = cur.fetchone()

        if row:
            if row["banned_until"]:
                try:
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
                    if ban_time > datetime.now(timezone.utc):
                        return jsonify({"error": "Account sospeso"}), 403
                except Exception:
                    pass
            user_id = row["id"]
            role = row["role"]
            username = row["username"]
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP, email = %s WHERE id = %s", (email, user_id))
            conn.commit()
            try:
                from storage import audit_log
                audit_log(user_id, "auth.google_login", f"{username} ({email})")
            except Exception:
                pass
            logger.info(f"Google login: {username} ({email})")
        else:
            user_id = str(uuid.uuid4())
            username = name
            base_name = username
            suffix = 1
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            while cur.fetchone():
                username = f"{base_name}{suffix}"
                suffix += 1
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            cur.execute(
                "INSERT INTO users (id, username, password_hash, role, google_id, email) VALUES (%s, %s, '', 'user', %s, %s)",
                (user_id, username, google_id, email)
            )
            conn.commit()

            if referral_code:
                from storage import claim_referral_bonus
                ok, msg = claim_referral_bonus(user_id, referral_code)
                if ok:
                    logger.info(f"Referral riscattato: {username} con codice {referral_code}")
                else:
                    logger.info(f"Referral non riscattato per {username}, codice {referral_code}: {msg}")

            try:
                from storage import init_new_user_bonus
                init_new_user_bonus(user_id)
                from storage import audit_log
                audit_log(user_id, "auth.google_register", f"{username} ({email})")
            except Exception:
                pass
            logger.info(f"Nuovo utente Google: {username} ({email})")
    finally:
        put_conn(conn)

    access_token, refresh_token = create_tokens(user_id, role if row else "user")
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user_id,
            "username": username,
            "role": role if row else "user",
            "email": email,
        }
    }), 200 if row else 201

# ─── Password login (fallback) ───────────────────────────────────
@auth_bp.route("/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    referral_code = data.get("referral_code", "").strip()

    if not username or not password:
        return jsonify({"error": "Username e password richiesti"}), 400
    if len(username) < 3 or len(username) > 20:
        return jsonify({"error": "Username deve essere 3-20 caratteri"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password minima 8 caratteri"}), 400
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return jsonify({"error": "Username solo lettere, numeri e underscore"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing = cur.fetchone()
        if existing:
            return jsonify({"error": "Username già in uso"}), 409

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password, method="scrypt")
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role) VALUES (%s, %s, %s, 'user')",
            (user_id, username, password_hash)
        )
        conn.commit()
    finally:
        put_conn(conn)

    if referral_code:
        from storage import claim_referral_bonus
        ok, msg = claim_referral_bonus(user_id, referral_code)
        if ok:
            logger.info(f"Referral riscattato: {username} con codice {referral_code}")
        else:
            logger.info(f"Referral non riscattato per {username}, codice {referral_code}: {msg}")

    access_token, refresh_token = create_tokens(user_id, "user")
    try:
        from storage import audit_log
        audit_log(user_id, "auth.register", username)
    except Exception:
        pass
    logger.info(f"Nuovo utente registrato: {username}")
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user_id,
            "username": username,
            "role": "user",
        }
    }), 201

@auth_bp.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username e password richiesti"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, password_hash, role, banned_until FROM users WHERE username = %s",
            (username,)
        )
        row = cur.fetchone()
    finally:
        put_conn(conn)

    if not row:
        return jsonify({"error": "Credenziali non valide"}), 401

    if not row["password_hash"]:
        return jsonify({"error": "Account registrato con Google, usa Accedi con Google"}), 401

    if row["banned_until"]:
        try:
            ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
            if ban_time > datetime.now(timezone.utc):
                return jsonify({"error": "Account sospeso fino al " + str(row["banned_until"])}), 403
        except Exception:
            pass

    if not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Credenziali non valide"}), 401

    access_token, refresh_token = create_tokens(row["id"], row["role"])
    conn2 = get_conn()
    try:
        cur2 = conn2.cursor()
        cur2.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (row["id"],))
        conn2.commit()
    finally:
        put_conn(conn2)
    try:
        from storage import audit_log
        audit_log(row["id"], "auth.login", username)
    except Exception:
        pass

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": row["id"],
            "username": username,
            "role": row["role"],
        }
    })

@auth_bp.route("/auth/local-login", methods=["POST"])
def local_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    referral_code = data.get("referral_code", "").strip()
    if not username:
        return jsonify({"error": "Username richiesto"}), 400
    if len(username) < 1 or len(username) > 30:
        return jsonify({"error": "Username 1-30 caratteri"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role, banned_until FROM users WHERE username = %s", (username,))
        row = cur.fetchone()

        if row:
            if row["banned_until"]:
                try:
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(row["banned_until"])
                    if ban_time > datetime.now(timezone.utc):
                        return jsonify({"error": "Account sospeso"}), 403
                except Exception:
                    pass
            user_id = row["id"]
            role = row["role"]
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
            conn.commit()
        else:
            user_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO users (id, username, password_hash, role) VALUES (%s, %s, '', 'user')",
                (user_id, username)
            )
            conn.commit()

            if referral_code:
                from storage import claim_referral_bonus
                ok, msg = claim_referral_bonus(user_id, referral_code)
                if ok:
                    logger.info(f"Referral riscattato: {username} con codice {referral_code}")
                else:
                    logger.info(f"Referral non riscattato per {username}, codice {referral_code}: {msg}")

            from storage import init_new_user_bonus
            init_new_user_bonus(user_id)
    finally:
        put_conn(conn)

    access_token, refresh_token = create_tokens(user_id, role if row else "user")
    try:
        from storage import audit_log
        audit_log(user_id, "auth.local_login", username)
    except Exception:
        pass
    logger.info(f"Local login: {username}")

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user_id,
            "username": username,
            "role": role if row else "user",
        }
    }), 200 if row else 201


@auth_bp.route("/auth/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token", "")
    if not refresh_token:
        return jsonify({"error": "Refresh token richiesto"}), 400

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, expires_at FROM refresh_tokens WHERE token_hash = %s", (token_hash,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Refresh token non valido"}), 401

        try:
            expires = row["expires_at"] if isinstance(row["expires_at"], datetime) else datetime.fromisoformat(row["expires_at"])
            if expires < datetime.now(timezone.utc):
                cur.execute("DELETE FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
                conn.commit()
                return jsonify({"error": "Refresh token scaduto"}), 401
        except Exception:
            pass

        cur.execute("DELETE FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
        conn.commit()

        cur.execute("SELECT role FROM users WHERE id = %s", (row["user_id"],))
        user_row = cur.fetchone()
        role = user_row["role"] if user_row else "user"
    finally:
        put_conn(conn)

    new_access, new_refresh = create_tokens(row["user_id"], role)
    return jsonify({
        "access_token": new_access,
        "refresh_token": new_refresh,
    })

@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if token:
        payload = _verify_jwt(token)
        if payload:
            with _blacklist_lock:
                _token_blacklist.add(payload.get("jti", ""))

    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token", "")
    if refresh_token:
        revoke_refresh_token(refresh_token)

    return jsonify({"status": "ok"})

# Pulizia token scaduti ogni ora
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
