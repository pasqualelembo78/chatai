import re
import uuid
import hashlib
from datetime import datetime as _dt, timezone as _tz

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from storage import init_new_user_bonus, audit_log
from db import get_conn, put_conn
from auth_fastapi import (
    AuthUser, create_tokens, ensure_persistent_token,
    GOOGLE_CLIENT_ID, _verify_google_token,
    generate_password_hash, check_password_hash,
    revoke_refresh_token, _verify_jwt, _blacklist_lock, _token_blacklist,
    reauth_from_persistent_token, require_adult,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth")


class GoogleLoginRequest(BaseModel):
    id_token: str = ""
    referral_code: str = ""
    birth_date: str = ""


class RegisterRequest(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""
    referral_code: str = ""
    birth_date: str = ""


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class LocalLoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    referral_code: str = ""
    birth_date: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str = ""


class LogoutRequest(BaseModel):
    refresh_token: str = ""


@router.get("/google/client-id")
async def google_client_id():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(404, "Google Sign-In non configurato")
    return {"client_id": GOOGLE_CLIENT_ID}


@router.post("/google")
@limiter.limit("10/minute")
async def google_login(request: Request, body: GoogleLoginRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google Sign-In non configurato sul server")
    if not body.id_token:
        raise HTTPException(400, "id_token richiesto")
    info = _verify_google_token(body.id_token)
    if not info:
        raise HTTPException(401, "Token Google non valido")

    google_id = info["sub"]
    email = info.get("email", "")
    name = info.get("name", email.split("@")[0] if email else "Utente")
    referral_code = body.referral_code.strip()

    conn = get_conn()
    row = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role, banned_until, username FROM users WHERE google_id = %s", (google_id,))
        row = cur.fetchone()

        if row:
            if row["banned_until"]:
                try:
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], _dt) else _dt.fromisoformat(str(row["banned_until"]))
                    if ban_time > _dt.now(_tz.utc):
                        raise HTTPException(403, "Account sospeso")
                except HTTPException:
                    raise
                except Exception:
                    pass
            user_id = row["id"]
            role = row["role"]
            username = row["username"]
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP, email = %s WHERE id = %s", (email, user_id))
            conn.commit()
            try:
                audit_log(user_id, "auth.google_login", f"{username} ({email})")
            except Exception:
                pass
        else:
            # Age verification only applies to new accounts.
            birth_date = require_adult(body.birth_date)
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
                "INSERT INTO users (id, username, password_hash, role, google_id, email, birth_date) VALUES (%s, %s, '', 'user', %s, %s, %s)",
                (user_id, username, google_id, email, birth_date)
            )
            conn.commit()
            if referral_code:
                from storage import claim_referral_bonus as _crb
                _crb(user_id, referral_code)
            try:
                init_new_user_bonus(user_id)
                audit_log(user_id, "auth.google_register", f"{username} ({email})")
            except Exception:
                pass
    finally:
        put_conn(conn)

    access_token, refresh_token = create_tokens(user_id, row["role"] if row else "user")
    persistent_token = ensure_persistent_token(user_id)
    status = 200 if row else 201
    return JSONResponse(
        status_code=status,
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "persistent_token": persistent_token,
            "user": {"id": user_id, "username": username, "role": row["role"] if row else "user", "email": email}
        }
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest):
    username = body.username.strip()
    password = body.password
    email = body.email.strip().lower()
    referral_code = body.referral_code.strip()
    if not username or not password:
        raise HTTPException(400, "Username e password richiesti")
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(400, "Username deve essere 3-20 caratteri")
    if len(password) < 8:
        raise HTTPException(400, "Password minima 8 caratteri")
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise HTTPException(400, "Username solo lettere, numeri e underscore")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Email non valida")

    # Age verification: only adults (>=18) may register.
    birth_date = require_adult(body.birth_date)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(409, "Username già in uso")
        if email:
            cur.execute("SELECT id FROM users WHERE email = %s AND email != ''", (email,))
            if cur.fetchone():
                raise HTTPException(409, "Email già registrata")
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password, method="scrypt")
        cur.execute("INSERT INTO users (id, username, password_hash, email, role, birth_date) VALUES (%s, %s, %s, %s, 'user', %s)",
                    (user_id, username, password_hash, email, birth_date))
        conn.commit()
    finally:
        put_conn(conn)

    if referral_code:
        from storage import claim_referral_bonus as _crb
        _crb(user_id, referral_code)

    access_token, refresh_token = create_tokens(user_id, "user")
    persistent_token = ensure_persistent_token(user_id)
    try:
        audit_log(user_id, "auth.register", username)
    except Exception:
        pass
    return JSONResponse(
        status_code=201,
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "persistent_token": persistent_token,
            "user": {"id": user_id, "username": username, "role": "user", "email": email}
        }
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    username = body.username.strip()
    password = body.password
    if not username or not password:
        raise HTTPException(400, "Username e password richiesti")

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, role, banned_until FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
    finally:
        put_conn(conn)

    if not row:
        raise HTTPException(401, "Credenziali non valide")
    if not row["password_hash"]:
        raise HTTPException(401, "Account registrato con Google, usa Accedi con Google")
    if row["banned_until"]:
        try:
            ban_time = row["banned_until"] if isinstance(row["banned_until"], __import__("datetime").datetime) else __import__("datetime").datetime.fromisoformat(str(row["banned_until"]))
            if ban_time > _dt.now(_tz.utc):
                raise HTTPException(403, f"Account sospeso fino al {row['banned_until']}")
        except HTTPException:
            raise
        except Exception:
            pass
    if not check_password_hash(row["password_hash"], password):
        raise HTTPException(401, "Credenziali non valide")

    access_token, refresh_token = create_tokens(row["id"], row["role"])
    persistent_token = ensure_persistent_token(row["id"])
    conn2 = get_conn()
    try:
        cur2 = conn2.cursor()
        cur2.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (row["id"],))
        conn2.commit()
    finally:
        put_conn(conn2)
    try:
        audit_log(row["id"], "auth.login", username)
    except Exception:
        pass

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "persistent_token": persistent_token,
        "user": {"id": row["id"], "username": username, "role": row["role"]}
    }


@router.post("/local-login")
@limiter.limit("5/minute")
async def local_login(request: Request, body: LocalLoginRequest):
    username = body.username.strip()
    password = body.password.strip()
    referral_code = body.referral_code.strip()
    if not username:
        raise HTTPException(400, "Username richiesto")
    if len(username) < 1 or len(username) > 30:
        raise HTTPException(400, "Username 1-30 caratteri")
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise HTTPException(400, "Username: solo lettere, numeri, underscore")
    if not password:
        raise HTTPException(400, "Password richiesta")
    if len(password) < 8:
        raise HTTPException(400, "Password minimo 8 caratteri")

    conn = get_conn()
    row = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, role, banned_until FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row:
            if row["banned_until"]:
                try:
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], __import__("datetime").datetime) else __import__("datetime").datetime.fromisoformat(str(row["banned_until"]))
                    if ban_time > _dt.now(_tz.utc):
                        raise HTTPException(403, "Account sospeso")
                except HTTPException:
                    raise
                except Exception:
                    pass
            if not row["password_hash"] or not check_password_hash(row["password_hash"], password):
                raise HTTPException(401, "Credenziali non valide")
            user_id = row["id"]
            role = row["role"]
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
            conn.commit()
        else:
            # Age verification only applies to new accounts.
            birth_date = require_adult(body.birth_date)
            user_id = str(uuid.uuid4())
            password_hash = generate_password_hash(password, method="scrypt")
            cur.execute("INSERT INTO users (id, username, password_hash, role, birth_date) VALUES (%s, %s, %s, 'user', %s)",
                        (user_id, username, password_hash, birth_date))
            conn.commit()
            if referral_code:
                from storage import claim_referral_bonus as _crb
                _crb(user_id, referral_code)
            init_new_user_bonus(user_id)
    finally:
        put_conn(conn)

    access_token, refresh_token = create_tokens(user_id, row["role"] if row else "user")
    persistent_token = ensure_persistent_token(user_id)
    try:
        audit_log(user_id, "auth.local_login", username)
    except Exception:
        pass
    return JSONResponse(
        status_code=200 if row else 201,
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "persistent_token": persistent_token,
            "user": {"id": user_id, "username": username, "role": row["role"] if row else "user"}
        }
    )


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh(request: Request, body: RefreshRequest):
    if not body.refresh_token:
        raise HTTPException(400, "Refresh token richiesto")
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id, expires_at FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(401, "Refresh token non valido")
        try:
            expires = row["expires_at"] if isinstance(row["expires_at"], _dt) else _dt.fromisoformat(str(row["expires_at"]))
            if expires < _dt.now(_tz.utc):
                cur.execute("DELETE FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
                conn.commit()
                raise HTTPException(401, "Refresh token scaduto")
        except HTTPException:
            raise
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
    return {"access_token": new_access, "refresh_token": new_refresh}


@router.post("/reauth")
@limiter.limit("5/minute")
async def reauth(request: Request):
    """Re-authenticate using persistent token (API key). Fallback when JWT + refresh both fail."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body richiesto")
    persistent_token = body.get("persistent_token", "")
    if not persistent_token:
        raise HTTPException(400, "persistent_token richiesto")
    result = reauth_from_persistent_token(persistent_token)
    if not result:
        raise HTTPException(401, "Persistent token non valido")
    access_token, refresh_token, user_id = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "persistent_token": persistent_token,
    }


@router.post("/logout")
async def logout(request: Request, body: LogoutRequest):
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if token:
        payload = _verify_jwt(token)
        if payload:
            with _blacklist_lock:
                _token_blacklist.add(payload.get("jti", ""))
    if body.refresh_token:
        revoke_refresh_token(body.refresh_token)
    return {"status": "ok"}
