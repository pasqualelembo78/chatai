import os
import sys

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _val = _line.split("=", 1)
            _key, _val = _key.strip(), _val.strip().strip("\"'").strip()
            if _val and not os.environ.get(_key):
                os.environ[_key] = _val

import json
import logging
import re
import uuid
import threading
import time
import base64
import hashlib
from typing import Optional
from functools import wraps

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, Depends, UploadFile, File, Form, Query, Body, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import socketio as socketio_lib

from characters import (get_character, list_characters, get_categories,
    get_characters_by_category, search_characters, get_adult_characters,
    filter_characters_by_gender)
from emotion_engine import (
    detect_emotion, detect_pressure, compute_intimacy_delta, compute_pressure_deltas)
from storage import (
    init_db, get_relationship, update_relationship,
    get_personality, update_personality, describe_personality,
    update_intimacy, update_pressure_level,
    get_world_state, save_world_state,
    add_message, get_recent_messages, count_messages, has_scenario_message,
    add_memory, get_memories, get_last_summary_checkpoint,
    record_personality_shift, get_recent_shifts,
    get_user_memory, update_user_memory, reset_user_memory,
    reset_conversation, reset_all_user_data,
    create_user_character, get_user_character, get_user_characters,
    get_all_user_characters, delete_user_character,
    is_user_premium, set_user_premium,
    get_evolution, update_evolution,
    get_user_preferences, save_user_preferences,
    get_mevacoins_balance, add_mevacoins,
    get_mevacoins_transactions,
    daily_checkin,
    get_new_user_bonus, claim_new_user_bonus, init_new_user_bonus,
    unlock_content, is_content_unlocked, get_user_unlocks,
    get_or_create_referral_code, get_referrer_by_code, claim_referral_bonus,
    credit_referral_first_message, get_daily_share_count, add_social_share,
    get_checkin_streak, claim_streak_milestone, count_all_user_messages,
    get_streak_30_status, claim_streak_30_day, calculate_streak_reward,
    # Phase 2-8: Per-user memory
    get_user_personality, update_user_personality as update_user_personality_db,
    set_user_personality,
    get_user_world_state, save_user_world_state,
    update_user_memory_enhanced, decay_user_memory, get_relevant_memories,
    start_conversation_session, get_temporal_context,
    share_memory_across_characters, get_shared_memories,
    detect_message_topics, update_conversation_topics, get_recent_topics,
    consolidate_user_memory, get_character_recent_topics,
)
from evolution_engine import evaluate_evolution
from prompt_builder import build_messages
from ai_engine import (get_ai_response, init_provider, get_providers,
    get_active_config, set_active, clear_model_cache,
    rebuild_free_model_chain, test_provider_connection)
import ai_engine
import audio_utils
import image_utils
import security_utils
from db import get_conn, put_conn
from auth_fastapi import (
    jwt_required, jwt_optional, admin_required, AuthUser,
    init_auth_db, socket_authenticate, create_tokens,
    GOOGLE_CLIENT_ID, _verify_google_token, _cleanup_expired_tokens,
    revoke_refresh_token, _verify_jwt, _blacklist_lock, _token_blacklist,
    generate_password_hash, check_password_hash,
    ensure_persistent_token, reauth_from_persistent_token,
)
from slowapi import Limiter
from slowapi.util import get_remote_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Rate limiter ────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ─── Socket.IO ───────────────────────────────────────────────────
sio = socketio_lib.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=30,
    ping_timeout=120,
    logger=False,
    engineio_logger=False,
)

user_sessions = {}
user_rooms = {}
user_names = {}
greeted_users = set()
socket_auth_map = {}

SUMMARY_INTERVAL = 30

MEDIA_COOLDOWNS = {}
MEDIA_COOLDOWN_SECONDS = 600

FEATURES = {
    "image_gen": {"name": "Generazione Immagini", "mvc_cost": 50},
    "video_gen": {"name": "Generazione Video", "mvc_cost": 100},
    "premium_voice": {"name": "Messaggi Vocali Premium", "mvc_cost": 30},
    "extended_memory": {"name": "Memoria Estesa", "mvc_cost": 80},
}

_CHAT_GEN_MODEL = "black-forest-labs/FLUX.1-schnell"
_CHAT_GEN_API_URL = "https://router.huggingface.co/hf-inference/models/"

@asynccontextmanager
async def lifespan(application):
    logger.info("Initializing database...")
    init_db()
    init_auth_db()
    from storage import init_group_chat_tables
    init_group_chat_tables()
    init_provider()
    rebuild_free_model_chain()
    threading.Thread(target=_cleanup_loop, daemon=True).start()
    threading.Thread(target=_cleanup_expired_tokens, daemon=True).start()
    threading.Thread(target=_free_port_background, args=(int(os.environ.get("PORT", 5000)),), daemon=True).start()
    logger.info("ChatAI FastAPI started")
    yield
    logger.info("ChatAI FastAPI shutting down")

app = FastAPI(title="ChatAI", docs_url="/docs", redoc_url=None, lifespan=lifespan)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

socket_app = socketio_lib.ASGIApp(sio, other_asgi_app=app)

# ─── Helpers ─────────────────────────────────────────────────────
def _send_alert(message):
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if telegram_bot_token and telegram_chat_id:
        try:
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage",
                json={"chat_id": telegram_chat_id, "text": f"[ChatAI] {message[:1000]}", "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")

def _cleanup_loop():
    while True:
        time.sleep(300)
        try:
            audio_utils.cleanup_old_files()
        except Exception:
            pass
        try:
            security_utils.cleanup_old_files()
        except Exception:
            pass

def _free_port_background(port):
    import subprocess, signal
    try:
        own_pid = os.getpid()
        time.sleep(1)
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split() if int(p) != own_pid]
            if pids:
                logger.warning(f"Port {port} in use by PIDs: {pids}. Killing...")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    except Exception:
        pass

def _free_port(port):
    import subprocess, signal
    try:
        own_pid = os.getpid()
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split() if int(p) != own_pid]
            if pids:
                logger.warning(f"Port {port} in use by PIDs: {pids}. Killing...")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
    except Exception:
        pass

# ─── Socket rate limiter ──────────────────────────────────────────
from collections import defaultdict as _dd
_user_rate_map = _dd(list)

def _socket_rate_limit(max_free=30, max_premium=120):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            sid = kwargs.get("sid") or (args[0] if args else None)
            uid = user_rooms.get(sid)
            if not uid:
                return await f(*args, **kwargs)
            now = time.time()
            window = now - 60
            _user_rate_map[uid] = [t for t in _user_rate_map[uid] if t > window]
            limit = max_premium if is_user_premium(uid) else max_free
            if len(_user_rate_map[uid]) >= limit:
                await sio.emit("stream error", {"message": "rate_limit"}, room=sid)
                return
            _user_rate_map[uid].append(now)
            return await f(*args, **kwargs)
        return wrapper
    return decorator

# ─── Pydantic models ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    character: Optional[str] = None
    text: str = ""
    username: str = "Utente"
    memory_context: Optional[list] = None
    user_memory: Optional[dict] = None
    character_data: Optional[dict] = None
    image: str = ""
    image_mime: str = "image/jpeg"
    is_favorite: bool = False
    client_storage: bool = False
    relationship_state: Optional[dict] = None
    personality_state: Optional[dict] = None
    evolution_state: Optional[dict] = None
    shifts: Optional[list] = None
    summaries: Optional[list] = None

class ConfigRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None

class TestRequest(BaseModel):
    provider: str = ""
    api_key: str = ""

class PremiumRequest(BaseModel):
    sku: str = ""
    purchase_token: str = ""

class BanRequest(BaseModel):
    user_id: str = ""
    hours: int = 0

class PruneRequest(BaseModel):
    days: int = 90

class ImportRequest(BaseModel):
    source: str = "charactercodex"
    count: int = 500
    genre: Optional[str] = None
    filepath: str = "backend/characters.py"

class DuplicatesRequest(BaseModel):
    filepath: str = "backend/characters.py"

class RoleRequest(BaseModel):
    role: str = "user"

class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    role: str = "user"

class MemoryUpdateRequest(BaseModel):
    facts: dict = {}

class SpendRequest(BaseModel):
    content_type: str = ""
    content_id: str = ""
    amount: int = 0

class ClaimBonusRequest(BaseModel):
    day: int = 1

class ClaimReferralRequest(BaseModel):
    code: str = ""

class ShareRequest(BaseModel):
    platform: str = ""

class CreateGroupChatRequest(BaseModel):
    name: str
    character_ids: list = []

class ReportRequest(BaseModel):
    reported_user: str = "unknown"
    character_id: str = ""
    message_text: str = ""

class TtsRequest(BaseModel):
    text: str = ""
    character_id: str = ""

class SuggestionRequest(BaseModel):
    character_id: str = ""

class UserPreferencesRequest(BaseModel):
    pass  # accepts any dict

class GoogleLoginRequest(BaseModel):
    id_token: str = ""
    referral_code: str = ""

class RegisterRequest(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""
    referral_code: str = ""

class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""

class LocalLoginRequest(BaseModel):
    username: str = ""
    referral_code: str = ""

class RefreshRequest(BaseModel):
    refresh_token: str = ""

class LogoutRequest(BaseModel):
    refresh_token: str = ""

class CreateCharacterRequest(BaseModel):
    name: str = ""
    age: int = 0
    model_config = {"extra": "allow"}

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Public
# ═══════════════════════════════════════════════════════════════════
@app.get("/")
async def index():
    return {
        "status": "running",
        "endpoints": {
            "register": "/auth/register (POST)",
            "login": "/auth/login (POST)",
            "refresh": "/auth/refresh (POST)",
            "logout": "/auth/logout (POST)",
            "providers": "/providers",
            "available_models": "/available-models",
            "categories": "/categories",
            "characters": "/characters",
            "character_detail": "/characters/<id>",
            "search": "/characters/search?q=<query>",
            "adult": "/characters/adult",
            "chat": "/chat (POST)",
            "transcribe": "/transcribe (POST)",
            "tts": "/tts (POST, JSON)",
            "voice_profile": "/voice-profile/<character_id>",
            "upload_image": "/upload-image (POST)",
            "config": "/config (GET/POST)",
            "memory": "/memory (GET/POST/DELETE)",
            "evolution": "/evolution?character_id=Y",
            "conversations": "/conversations",
            "premium": "/premium/check",
            "stream_chat": "Socket.IO con token auth"
        }
    }

@app.get("/categories")
async def api_categories(
    adult: str = Query("false"),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    is_adult = adult.lower() == "true"
    if not is_adult and user:
        try:
            prefs = get_user_preferences(user.user_id)
            is_adult = prefs.get("show_adult", False)
        except Exception:
            pass
    cats = get_categories()
    unlocks = set()
    if user:
        try:
            prefs = get_user_preferences(user.user_id)
            unlocks = {u["content_id"] for u in get_user_unlocks(user.user_id) if u["content_type"] == "category"}
        except Exception:
            pass
    result = []
    for c in cats:
        entry = dict(c)
        mvc_cost = c.get("mvc_cost", 0)
        entry["locked"] = mvc_cost > 0 and c["id"] not in unlocks
        # Count characters in this category
        from characters import get_characters_by_category
        try:
            entry["character_count"] = len(get_characters_by_category(c["id"]))
        except Exception:
            entry["character_count"] = 0
        result.append(entry)
    return result

@app.get("/providers")
async def api_providers():
    return get_providers()

@app.get("/available-models")
async def api_available_models():
    chain = ai_engine.FREE_MODEL_CHAIN
    grouped = {}
    seen = set()
    for pid, model in chain:
        if pid not in grouped:
            grouped[pid] = []
        key = f"{pid}/{model}"
        if key not in seen:
            seen.add(key)
            name = model
            provider = ai_engine.PROVIDERS.get(pid)
            if provider:
                for m in provider.get("models", []):
                    if m["id"] == model:
                        name = m.get("name", model)
                        break
            grouped[pid].append({"id": model, "name": name})
    return grouped

@app.get("/voice-profile/{character_id}")
async def api_voice_profile(character_id: str):
    char = get_character(character_id)
    if not char:
        raise HTTPException(404, "character not found")
    return audio_utils.get_voice_profile(char)

@app.get("/privacy")
async def api_privacy():
    return {
        "version": "1.0",
        "updated_at": "2026-07-06",
        "text": (
            "PRIVACY POLICY — ChatAI\n\n"
            "1. DATI RACCOLTI: username, email (se Google Sign-In), messaggi di chat, "
            "registrazioni audio (solo per trascrizione), immagini caricate (solo per descrizione AI).\n\n"
            "2. FINALITÀ: fornire il servizio di chat AI, migliorare i modelli di conversazione, "
            "assistenza tecnica.\n\n"
            "3. BASE GIURIDICA: consenso esplicito dell'utente (art. 6 GDPR).\n\n"
            "4. CONDIVISIONE: i dati NON vengono venduti a terzi. Le richieste AI vengono inviate "
            "a provider esterni (Groq, Google Gemini, OpenAI, ecc.) senza dati identificativi.\n\n"
            "5. CONSERVAZIONE: messaggi fino a 90 giorni. Log di audit fino a 365 giorni. "
            "I file audio/immagini vengono eliminati dopo 5 minuti.\n\n"
            "6. DIRITTI: accesso, rettifica, cancellazione (diritto all'oblio), limitazione, "
            "portabilità dei dati. Endpoint: GET /user/export, POST /user/delete.\n\n"
            "7. CONTATTI: per esercitare i tuoi diritti, contatta l'amministratore.\n\n"
            "8. MODIFICHE: la policy verrà aggiornata con preavviso di 30 giorni."
        )
    }

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Auth
# ═══════════════════════════════════════════════════════════════════
@app.get("/auth/google/client-id")
async def google_client_id():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(404, "Google Sign-In non configurato")
    return {"client_id": GOOGLE_CLIENT_ID}

@app.post("/auth/google")
async def google_login(body: GoogleLoginRequest):
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
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], datetime) else datetime.fromisoformat(str(row["banned_until"]))
                    from datetime import datetime as _dt, timezone as _tz
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
                from storage import audit_log
                audit_log(user_id, "auth.google_login", f"{username} ({email})")
            except Exception:
                pass
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
                from storage import claim_referral_bonus as _crb
                _crb(user_id, referral_code)
            try:
                init_new_user_bonus(user_id)
                from storage import audit_log
                audit_log(user_id, "auth.google_register", f"{username} ({email})")
            except Exception:
                pass
    finally:
        put_conn(conn)

    from datetime import datetime as _dt
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

@app.post("/auth/register")
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
        cur.execute("INSERT INTO users (id, username, password_hash, email, role) VALUES (%s, %s, %s, %s, 'user')",
                    (user_id, username, password_hash, email))
        conn.commit()
    finally:
        put_conn(conn)

    if referral_code:
        from storage import claim_referral_bonus as _crb
        _crb(user_id, referral_code)

    access_token, refresh_token = create_tokens(user_id, "user")
    persistent_token = ensure_persistent_token(user_id)
    try:
        from storage import audit_log
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

@app.post("/auth/login")
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
            from datetime import datetime as _dt, timezone as _tz
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
        from storage import audit_log
        audit_log(row["id"], "auth.login", username)
    except Exception:
        pass

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "persistent_token": persistent_token,
        "user": {"id": row["id"], "username": username, "role": row["role"]}
    }

@app.post("/auth/local-login")
async def local_login(body: LocalLoginRequest):
    username = body.username.strip()
    referral_code = body.referral_code.strip()
    if not username:
        raise HTTPException(400, "Username richiesto")
    if len(username) < 1 or len(username) > 30:
        raise HTTPException(400, "Username 1-30 caratteri")

    conn = get_conn()
    row = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role, banned_until FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row:
            if row["banned_until"]:
                try:
                    ban_time = row["banned_until"] if isinstance(row["banned_until"], __import__("datetime").datetime) else __import__("datetime").datetime.fromisoformat(str(row["banned_until"]))
                    from datetime import datetime as _dt, timezone as _tz
                    if ban_time > _dt.now(_tz.utc):
                        raise HTTPException(403, "Account sospeso")
                except HTTPException:
                    raise
                except Exception:
                    pass
            user_id = row["id"]
            role = row["role"]
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
            conn.commit()
        else:
            user_id = str(uuid.uuid4())
            cur.execute("INSERT INTO users (id, username, password_hash, role) VALUES (%s, %s, '', 'user')",
                        (user_id, username))
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
        from storage import audit_log
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

@app.post("/auth/refresh")
async def refresh(body: RefreshRequest):
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
        from datetime import datetime as _dt, timezone as _tz
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

@app.post("/auth/reauth")
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

@app.post("/auth/logout")
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

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Protected
# ═══════════════════════════════════════════════════════════════════
@app.get("/config")
async def api_config(user: AuthUser = Depends(jwt_required)):
    return get_active_config(user_id=user.user_id)

@app.post("/config")
async def api_set_config(body: ConfigRequest, user: AuthUser = Depends(jwt_required)):
    if body.provider:
        set_active(user.user_id, body.provider, body.model)
    return {"status": "ok", "config": get_active_config(user_id=user.user_id)}

@app.post("/refresh-models")
async def api_refresh_models(user: AuthUser = Depends(jwt_required)):
    clear_model_cache()
    rebuild_free_model_chain()
    return {"status": "ok", "chain": [f"{p}/{m}" for p, m in ai_engine.FREE_MODEL_CHAIN]}

@app.post("/api/test")
async def api_test(body: TestRequest, user: AuthUser = Depends(jwt_required)):
    if not body.provider:
        raise HTTPException(400, "provider richiesto")
    success, message = test_provider_connection(body.provider, body.api_key)
    return {"success": success, "message": message}

@app.get("/premium/check")
async def api_premium_check(user: AuthUser = Depends(jwt_required)):
    return {"is_premium": is_user_premium(user.user_id)}

@app.post("/premium/activate")
async def api_premium_activate(body: PremiumRequest, request: Request, user: AuthUser = Depends(jwt_required)):
    set_user_premium(user.user_id, True, body.sku, body.purchase_token)
    from storage import audit_log
    audit_log(user.user_id, "premium.activate", f"sku={body.sku}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "is_premium": True}

@app.get("/avatars/{char_id}")
async def api_avatar(char_id: str):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    category = char.get("category", "")
    avatar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "avatars", category, f"{char_id}.png")
    if not os.path.isfile(avatar_path):
        raise HTTPException(404, "avatar not found")
    return FileResponse(avatar_path, media_type="image/png")

@app.get("/characters")
async def api_characters(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    user_id = user.user_id if user else None
    if category == "per_te":
        from characters import list_characters as _lc
        all_chars = _lc()
        if user_id:
            prefs = get_user_preferences(user_id)
            interests = [t.lower() for t in prefs.get("interest_tags", [])]
            if interests:
                matching = [c for c in all_chars if any(t.lower() in interests for t in c.get("tags", []))]
                rest = [c for c in all_chars if c not in matching]
                chars = matching + rest
            else:
                chars = all_chars
        else:
            chars = all_chars
    else:
        chars = get_characters_by_category(category) if category else list_characters()

    if user_id:
        unlocks = {u["content_id"] for u in get_user_unlocks(user_id) if u["content_type"] == "category"}
        categories = get_categories()
        cat_cost = {c["id"]: c.get("mvc_cost", 0) for c in categories}
        chars = [c for c in chars if not cat_cost.get(c.get("category"), 0) or c["category"] in unlocks]
        try:
            prefs = get_user_preferences(user_id)
            gender = prefs.get("gender_interest", "")
            age_range = prefs.get("age_range", "")
            age_min, age_max = 0, 999
            if age_range:
                if "+" in age_range:
                    age_min = int(age_range.replace("+", ""))
                elif "-" in age_range:
                    parts = age_range.split("-")
                    age_min, age_max = int(parts[0]), int(parts[1])
            has_gender = gender and gender != "non binario"
            has_age = bool(age_range)
            if has_age or has_gender:
                from characters import infer_character_sex
                def _age_match(c):
                    return age_min <= c.get("age", 0) <= age_max
                def _gender_match(c):
                    return infer_character_sex(c) == gender
                def _unknown_gender(c):
                    return infer_character_sex(c) == ""
                if has_age and has_gender:
                    p1 = [c for c in chars if _age_match(c) and _gender_match(c)]
                    p2 = [c for c in chars if _age_match(c) and not _gender_match(c)]
                    p3 = [c for c in chars if not _age_match(c) and _gender_match(c)]
                    p4 = [c for c in chars if _age_match(c) and _unknown_gender(c)]
                    p5 = [c for c in chars if not _age_match(c) and _unknown_gender(c)]
                    p6 = [c for c in chars if not _age_match(c) and not _gender_match(c) and not _unknown_gender(c)]
                    chars = p1 + p2 + p3 + p4 + p5 + p6
                elif has_age:
                    chars = [c for c in chars if _age_match(c)] + [c for c in chars if not _age_match(c)]
                elif has_gender:
                    chars = ([c for c in chars if _gender_match(c)] +
                             [c for c in chars if _unknown_gender(c)] +
                             [c for c in chars if not _gender_match(c) and not _unknown_gender(c)])
        except Exception:
            pass
    return chars[offset:offset + limit]

@app.get("/characters/search")
async def api_search_characters(
    q: str = Query(""),
    category: Optional[str] = Query(None),
    user: Optional[AuthUser] = Depends(jwt_optional),
):
    q = q.strip()
    if not q:
        return []
    results = search_characters(q)
    if category:
        results = [c for c in results if c.get("category") == category]
    user_id = user.user_id if user else None
    if user_id:
        try:
            prefs = get_user_preferences(user_id)
            gender = prefs.get("gender_interest", "")
            if gender and gender != "non binario":
                from characters import infer_character_sex
                matching = [c for c in results if infer_character_sex(c) == gender]
                unknown = [c for c in results if infer_character_sex(c) == ""]
                rest = [c for c in results if infer_character_sex(c) not in (gender, "")]
                results = matching + unknown + rest
        except Exception:
            pass
    return results

@app.get("/characters/{char_id}")
async def api_character_detail(char_id: str):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    if "hobbies" in char and isinstance(char["hobbies"], list):
        formatted = []
        for h in char["hobbies"]:
            if isinstance(h, dict):
                skill = h.get("skill", "")
                formatted.append(f"{h['name']} ({skill})" if skill else h["name"])
            else:
                formatted.append(str(h))
        char = {**char, "hobbies": formatted}
    return char

@app.get("/characters/{char_id}/core")
async def api_character_core(char_id: str):
    char = get_character(char_id)
    if not char:
        raise HTTPException(404, "not found")
    core_fields = [
        "id", "name", "full_name", "surname", "age", "role", "category",
        "avatar", "description", "tags", "essence", "personality",
        "personality_profile", "speaking_style", "backstory",
        "hobbies", "possessions", "core_traits", "evolution",
        "refusal_style", "intimacy_config",
        "knowledge_domains", "personality_depth", "family",
        "education", "occupation", "childhood", "system_prompt",
    ]
    return {k: char.get(k) for k in core_fields if k in char}

@app.get("/characters/adult")
async def api_adult_characters(user: Optional[AuthUser] = Depends(jwt_optional)):
    chars = get_adult_characters()
    user_id = user.user_id if user else None
    if not user_id:
        return []
    unlocks = {u["content_id"] for u in get_user_unlocks(user_id) if u["content_type"] == "category"}
    cats = get_categories()
    cat_cost = {c["id"]: c.get("mvc_cost", 0) for c in cats}
    chars = [c for c in chars if not cat_cost.get(c.get("category"), 0) or c["category"] in unlocks]
    try:
        prefs = get_user_preferences(user_id)
        gender = prefs.get("gender_interest", "")
        if gender and gender != "non binario":
            from characters import infer_character_sex
            matching = [c for c in chars if infer_character_sex(c) == gender]
            unknown = [c for c in chars if infer_character_sex(c) == ""]
            rest = [c for c in chars if infer_character_sex(c) not in (gender, "")]
            chars = matching + unknown + rest
    except Exception:
        pass
    return chars

@app.post("/characters", status_code=201)
async def api_create_character(
    request: Request,
    body: CreateCharacterRequest,
    user: AuthUser = Depends(jwt_required),
):
    data = body.dict()
    if not data.get("name"):
        raise HTTPException(400, "name required")
    age = data.get("age", 0)
    if not isinstance(age, int) or age < 18:
        raise HTTPException(400, "L'età deve essere almeno 18 anni")
    char = create_user_character(user.user_id, data)
    from storage import audit_log
    audit_log(user.user_id, "character.create", char['id'],
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return char

@app.get("/characters/user")
async def api_user_characters(user: AuthUser = Depends(jwt_required)):
    return get_user_characters(user.user_id)

@app.delete("/characters/{char_id}")
async def api_delete_character(char_id: str, user: AuthUser = Depends(jwt_required)):
    char = get_character(char_id)
    if char and char.get("user_created"):
        delete_user_character(char_id)
        return {"status": "deleted"}
    raise HTTPException(404, "not found or not deletable")

@app.get("/memory")
async def api_get_memory(user: AuthUser = Depends(jwt_required)):
    return get_user_memory(user.user_id)

@app.post("/memory")
async def api_update_memory(body: MemoryUpdateRequest, user: AuthUser = Depends(jwt_required)):
    if not body.facts:
        raise HTTPException(400, "facts required")
    memory = update_user_memory(user.user_id, body.facts)
    return {"status": "ok", "memory": memory}

@app.delete("/memory")
async def api_reset_memory(user: AuthUser = Depends(jwt_required)):
    reset_user_memory(user.user_id)
    return {"status": "memory_reset"}

@app.get("/evolution")
async def api_get_evolution(
    character_id: str = Query(""),
    user: AuthUser = Depends(jwt_required),
):
    if not character_id:
        raise HTTPException(400, "character_id required")
    evo = get_evolution(user.user_id, character_id)
    char = get_character(character_id)
    stages = char.get("evolution", {}).get("stages", []) if char else []
    return {"evolution": evo, "stages": stages}

# ─── Conversations ────────────────────────────────────────────────
@app.get("/conversations")
async def api_get_conversations(user: AuthUser = Depends(jwt_required)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT character_id, COUNT(*) as msg_count, MAX(timestamp) as last_active "
            "FROM messages WHERE user_id=%s GROUP BY character_id ORDER BY last_active DESC",
            (user.user_id,)
        )
        rows = cur.fetchall()
    finally:
        put_conn(conn)
    result = []
    for r in rows:
        char = get_character(r["character_id"])
        if char:
            result.append({
                "character_id": r["character_id"],
                "character_name": char["name"],
                "character_avatar": char.get("avatar", "💬"),
                "message_count": r["msg_count"],
                "last_active": r["last_active"]
            })
    return result

@app.get("/conversations/{character_id}")
async def api_get_conversation(character_id: str, user: AuthUser = Depends(jwt_required)):
    msgs = get_recent_messages(user.user_id, character_id, limit=1000)
    return {"character_id": character_id, "messages": msgs}

@app.post("/conversations/{character_id}/reset")
async def api_reset_conversation(character_id: str, user: AuthUser = Depends(jwt_required)):
    reset_conversation(user.user_id, character_id)
    return {"status": "conversation_reset", "character_id": character_id}

# ─── User data ───────────────────────────────────────────────────
@app.post("/user/reset")
async def api_reset_user(user: AuthUser = Depends(jwt_required)):
    reset_all_user_data(user.user_id)
    return {"status": "all_data_reset"}

@app.get("/user/export")
async def api_export_user(request: Request, user: AuthUser = Depends(jwt_required)):
    from storage import export_user_data, audit_log
    data = export_user_data(user.user_id)
    audit_log(user.user_id, "user.export", "exported all data",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return data

@app.post("/user/delete")
async def api_delete_user(request: Request, user: AuthUser = Depends(jwt_required)):
    from storage import delete_user, audit_log
    audit_log(user.user_id, "user.delete", "account deleted",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    delete_user(user.user_id)
    return {"status": "account_deleted"}

@app.post("/user/report")
async def api_user_report(request: Request, body: ReportRequest, user: AuthUser = Depends(jwt_required)):
    from storage import flag_user, audit_log
    flag_user(
        user_id=body.reported_user,
        reason="Segnalazione utente",
        content_type=body.character_id,
        content_snippet=body.message_text,
        severity="medium",
        flagged_by=user.user_id
    )
    audit_log(user.user_id, "user.report", f"character={body.character_id}")
    return JSONResponse(status_code=201, content={"status": "ok"})

# ─── Preferences & Mevacoins ──────────────────────────────────────
@app.get("/user/preferences")
async def api_get_preferences(user: AuthUser = Depends(jwt_required)):
    return get_user_preferences(user.user_id)

@app.put("/user/preferences")
async def api_save_preferences(request: Request, user: AuthUser = Depends(jwt_required)):
    data = await request.json()
    save_user_preferences(user.user_id, data)
    from storage import audit_log
    audit_log(user.user_id, "preferences.update", json.dumps(data),
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok"}

@app.get("/user/mevacoins")
async def api_mevacoins_balance(user: AuthUser = Depends(jwt_required)):
    return {"balance": get_mevacoins_balance(user.user_id)}

@app.get("/user/mevacoins/unlocks")
async def api_mevacoins_unlocks(user: AuthUser = Depends(jwt_required)):
    unlocks = get_user_unlocks(user.user_id)
    unlocked_ids = {u["content_id"] for u in unlocks if u["content_type"] == "category"}
    unlocked_features = {u["content_id"] for u in unlocks if u["content_type"] == "feature"}
    return {
        "categories": list(unlocked_ids),
        "features": list(unlocked_features),
        "all": unlocks,
    }

@app.get("/user/mevacoins/transactions")
async def api_mevacoins_tx(user: AuthUser = Depends(jwt_required)):
    return get_mevacoins_transactions(user.user_id)

@app.post("/user/mevacoins/checkin")
async def api_daily_checkin(request: Request, user: AuthUser = Depends(jwt_required)):
    import logging
    log = logging.getLogger(__name__)
    try:
        success, earned, msg = claim_streak_30_day(user.user_id)
        log.info(f"checkin user={user.user_id} success={success} earned={earned} msg={msg}")
    except Exception as e:
        log.error(f"checkin FAILED user={user.user_id} error={e}")
        raise HTTPException(500, f"checkin error: {e}")
    if success:
        from storage import audit_log
        audit_log(user.user_id, "mevacoins.checkin", f"streak day earned={earned}",
                  request.client.host if request.client else "",
                  request.headers.get("User-Agent", ""))
    status = get_streak_30_status(user.user_id)
    return {
        "already_checked": not success,
        "earned": earned if success else 0,
        "streak": status["current_day"],
        "reward": status["reward"],
        "total_earned": status["total_earned"],
    }

@app.post("/user/mevacoins/spend")
async def api_mevacoins_spend(request: Request, body: SpendRequest, user: AuthUser = Depends(jwt_required)):
    if not body.content_type or not body.content_id or body.amount <= 0:
        raise HTTPException(400, "richiesta non valida")
    if body.content_type == "category":
        valid = any(c["id"] == body.content_id and c.get("mvc_cost", 0) == body.amount for c in get_categories())
        if not valid:
            raise HTTPException(400, "categoria o costo non valido")
    elif body.content_type == "feature":
        feat = FEATURES.get(body.content_id)
        if not feat or feat["mvc_cost"] != body.amount:
            raise HTTPException(400, "feature o costo non valido")
    else:
        raise HTTPException(400, "content_type non valido")
    if is_content_unlocked(user.user_id, body.content_type, body.content_id):
        return {"status": "ok", "unlocked": True, "already_unlocked": True}
    ok, msg = unlock_content(user.user_id, body.content_type, body.content_id, body.amount)
    if not ok:
        raise HTTPException(400 if msg == "saldo_insufficiente" else 500, msg)
    from storage import audit_log
    audit_log(user.user_id, "mevacoins.spend", f"{body.content_type}:{body.content_id} cost={body.amount}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "unlocked": True}

@app.get("/user/mevacoins/new-user-bonus")
async def api_new_user_bonus(user: AuthUser = Depends(jwt_required)):
    return get_new_user_bonus(user.user_id)

@app.post("/user/mevacoins/new-user-bonus/claim")
async def api_claim_bonus(body: ClaimBonusRequest, user: AuthUser = Depends(jwt_required)):
    ok = claim_new_user_bonus(user.user_id, body.day)
    return {"claimed": ok}

@app.get("/user/referral/code")
async def api_referral_code(user: AuthUser = Depends(jwt_required)):
    code = get_or_create_referral_code(user.user_id)
    if not code:
        raise HTTPException(500, "errore generazione codice")
    return {"code": code}

@app.post("/user/referral/claim")
async def api_claim_referral(request: Request, body: ClaimReferralRequest, user: AuthUser = Depends(jwt_required)):
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(400, "codice richiesto")
    ok, msg = claim_referral_bonus(user.user_id, code)
    if not ok:
        raise HTTPException(400, msg)
    from storage import audit_log
    audit_log(user.user_id, "referral.claim", f"code={code}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "bonus": 50}

@app.post("/user/mevacoins/share")
async def api_social_share(request: Request, body: ShareRequest, user: AuthUser = Depends(jwt_required)):
    ok, msg = add_social_share(user.user_id, body.platform)
    if not ok:
        raise HTTPException(400 if msg == "limite_giornaliero" else 500, msg)
    from storage import audit_log
    audit_log(user.user_id, "mevacoins.share", f"platform={body.platform}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "earned": 30}

@app.get("/user/mevacoins/share/status")
async def api_share_status(user: AuthUser = Depends(jwt_required)):
    count = get_daily_share_count(user.user_id)
    return {"today_count": count, "max_daily": 3}

@app.get("/user/mevacoins/streak")
async def api_streak_30(user: AuthUser = Depends(jwt_required)):
    return get_streak_30_status(user.user_id)

@app.post("/user/mevacoins/streak/claim")
async def api_streak_30_claim(request: Request, user: AuthUser = Depends(jwt_required)):
    success, earned, msg = claim_streak_30_day(user.user_id)
    if not success:
        if msg == "gia_riscosso":
            raise HTTPException(400, "Già riscosso oggi")
        raise HTTPException(500, msg)
    from storage import audit_log
    audit_log(user.user_id, "mevacoins.streak_claim", f"day={earned}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"earned": earned, "success": True}

@app.post("/chat/suggestion")
async def api_chat_suggestion(body: SuggestionRequest, user: Optional[AuthUser] = Depends(jwt_optional)):
    char = get_character(body.character_id)
    if not char:
        raise HTTPException(404, "character not found")
    tags_str = "generali"
    if user:
        prefs = get_user_preferences(user.user_id)
        tags = prefs.get("interest_tags", [])
        tags_str = ", ".join(tags) if tags else "generali"
    prompt = (
        f"Genera UNA domanda o frase di apertura che l'utente potrebbe inviare al personaggio '{char['name']}' "
        f"per iniziare una conversazione interessante. "
        f"La domanda deve essere naturale, in italiano, e tenere conto che l'utente ha questi interessi: {tags_str}. "
        f"Il personaggio è: {char.get('essence', 'un personaggio virtuale')}. "
        f"Restituisci SOLO la domanda, senza prefazioni o spiegazioni."
    )
    from ai_engine import get_ai_response as _gair
    uid = user.user_id if user else "anonymous"
    suggestion, _, _ = _gair([
        {"role": "system", "content": "Sei un assistente che genera domande di apertura per chat con personaggi virtuali. Rispondi solo con la domanda, nient'altro."},
        {"role": "user", "content": prompt}
    ], user_id=uid)
    if not suggestion:
        import random
        fallbacks = [f"Ciao {char['name']}! Come stai?", f"Raccontami qualcosa di te, {char['name']}.", f"Che cosa ti appassiona di più, {char['name']}?"]
        suggestion = random.choice(fallbacks)
    return {"suggestion": suggestion.strip()}

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Admin
# ═══════════════════════════════════════════════════════════════════
@app.get("/admin/users")
async def admin_list_users(user: AuthUser = Depends(admin_required)):
    from storage import get_all_users
    return get_all_users()

@app.post("/admin/ban")
async def admin_ban_user(request: Request, body: BanRequest, user: AuthUser = Depends(admin_required)):
    if not body.user_id:
        raise HTTPException(400, "user_id richiesto")
    from storage import ban_user, audit_log
    ban_user(body.user_id, body.hours)
    detail = f"banned for {body.hours}h" if body.hours > 0 else "unbanned"
    audit_log(user.user_id, "admin.ban", f"user={body.user_id} {detail}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "detail": detail}

@app.post("/admin/prune")
async def admin_prune(request: Request, body: PruneRequest, user: AuthUser = Depends(admin_required)):
    from storage import prune_old_data, audit_log
    result = prune_old_data(body.days)
    audit_log(user.user_id, "admin.prune", f"days={body.days} result={result}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "pruned": result}

@app.get("/admin/logs")
async def admin_logs(limit: int = Query(100), user: AuthUser = Depends(admin_required)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (min(limit, 1000),))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)

@app.get("/admin/flags")
async def admin_flags(resolved: str = Query("false"), user: AuthUser = Depends(admin_required)):
    from storage import get_moderation_flags
    return get_moderation_flags(resolved=resolved.lower() == "true")

@app.post("/admin/flags/{flag_id}/resolve")
async def admin_resolve_flag(flag_id: int, request: Request, user: AuthUser = Depends(admin_required)):
    from storage import resolve_moderation_flag, audit_log
    resolve_moderation_flag(flag_id)
    audit_log(user.user_id, "admin.resolve_flag", f"flag_id={flag_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "resolved", "flag_id": flag_id}

@app.get("/admin/import/sources")
async def admin_import_sources(user: AuthUser = Depends(admin_required)):
    from import_engine import SOURCES
    return list(SOURCES.values())

@app.post("/admin/import/start")
async def admin_import_start(request: Request, body: ImportRequest, user: AuthUser = Depends(admin_required)):
    from import_engine import start_import
    result = start_import(body.source, count=min(body.count, 16000), genre_filter=body.genre, filepath=body.filepath)
    if "error" in result:
        raise HTTPException(400, result["error"])
    from storage import audit_log
    audit_log(user.user_id, "admin.import_start", f"source={body.source} count={body.count}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result

@app.get("/admin/import/status")
async def admin_import_status(user: AuthUser = Depends(admin_required)):
    from import_engine import get_import_status
    return get_import_status()

@app.get("/admin/duplicates")
async def admin_duplicates(filepath: str = Query("backend/characters.py"), user: AuthUser = Depends(admin_required)):
    from import_engine import find_duplicates
    duplicates = find_duplicates(filepath)
    return {"total_duplicates": len(duplicates), "duplicates": duplicates[:100]}

@app.post("/admin/duplicates/clean")
async def admin_clean_duplicates(request: Request, body: DuplicatesRequest, user: AuthUser = Depends(admin_required)):
    from import_engine import clean_duplicates
    result = clean_duplicates(body.filepath)
    from storage import audit_log
    audit_log(user.user_id, "admin.clean_duplicates", f"result={result}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result

# ─── Endpoint admin extra: stats, search, detail, role, characters ─
@app.get("/admin/stats")
async def admin_stats(user: AuthUser = Depends(admin_required)):
    from storage import get_admin_stats
    return get_admin_stats()

@app.get("/admin/users/search")
async def admin_search_users(q: str = Query(""), user: AuthUser = Depends(admin_required)):
    from storage import search_users
    if not q:
        return []
    return search_users(q)

@app.get("/admin/users/{user_id}")
async def admin_user_detail(user_id: str, user: AuthUser = Depends(admin_required)):
    from storage import get_user_detail
    detail = get_user_detail(user_id)
    if not detail:
        raise HTTPException(404, "Utente non trovato")
    return detail

@app.put("/admin/users/{user_id}/role")
async def admin_update_role(user_id: str, request: Request, body: RoleRequest, user: AuthUser = Depends(admin_required)):
    if body.role not in ("user", "moderator", "admin"):
        raise HTTPException(400, "Ruolo non valido")
    from storage import update_user_role, audit_log
    ok = update_user_role(user_id, body.role)
    if not ok:
        raise HTTPException(404, "Utente non trovato")
    audit_log(user.user_id, "admin.role_change", f"user={user_id} role={body.role}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "user_id": user_id, "role": body.role}

@app.post("/admin/users")
async def admin_create_user(request: Request, body: CreateUserRequest, user: AuthUser = Depends(admin_required)):
    username = body.username.strip()
    password = body.password
    email = body.email.strip().lower()
    role = body.role
    if not username or not password:
        raise HTTPException(400, "Username e password richiesti")
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(400, "Username deve essere 3-20 caratteri")
    if len(password) < 8:
        raise HTTPException(400, "Password minima 8 caratteri")
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise HTTPException(400, "Username solo lettere, numeri e underscore")
    if role not in ("user", "moderator", "admin"):
        raise HTTPException(400, "Ruolo non valido")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Email non valida")
    from storage import get_conn, put_conn
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
        new_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password, method="scrypt")
        cur.execute("INSERT INTO users (id, username, password_hash, email, role) VALUES (%s, %s, %s, %s, %s)",
                    (new_id, username, password_hash, email, role))
        conn.commit()
    finally:
        put_conn(conn)
    from storage import audit_log
    audit_log(user.user_id, "admin.create_user", f"username={username} role={role}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "user_id": new_id, "username": username, "role": role}

@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request, user: AuthUser = Depends(admin_required)):
    from storage import delete_user, get_user_detail, audit_log
    target = get_user_detail(user_id)
    if not target:
        raise HTTPException(404, "Utente non trovato")
    if target.get("role") == "admin":
        raise HTTPException(403, "Non puoi eliminare un amministratore")
    delete_user(user_id)
    audit_log(user.user_id, "admin.delete_user", f"deleted={user_id} username={target.get('username','?')}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "deleted": user_id}

@app.get("/admin/characters")
async def admin_list_characters(user: AuthUser = Depends(admin_required)):
    from storage import get_all_user_characters
    chars = get_all_user_characters()
    return [{"id": c.get("id"), "name": c.get("name"), "category": c.get("category"),
             "user_id": c.get("user_id"), "is_adult": c.get("is_adult", False),
             "created_at": c.get("created_at")} for c in chars]

@app.delete("/admin/characters/{char_id}")
async def admin_delete_character(char_id: str, request: Request, user: AuthUser = Depends(admin_required)):
    from storage import delete_user_character, audit_log
    delete_user_character(char_id)
    audit_log(user.user_id, "admin.delete_character", f"char_id={char_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "deleted": char_id}

@app.get("/admin/users/{user_id}/conversations")
async def admin_user_conversations(user_id: str, user: AuthUser = Depends(admin_required)):
    from storage import list_user_conversations
    convs = list_user_conversations(user_id)
    result = []
    for c in convs:
        char = get_character(c["character_id"])
        result.append({
            "character_id": c["character_id"],
            "character_name": char["name"] if char else c["character_id"],
            "msg_count": c["msg_count"],
            "first_msg": str(c["first_msg"]) if c.get("first_msg") else None,
            "last_msg": str(c["last_msg"]) if c.get("last_msg") else None,
        })
    return result

@app.get("/admin/users/{user_id}/conversations/{character_id}")
async def admin_user_conversation_messages(user_id: str, character_id: str, user: AuthUser = Depends(admin_required)):
    from storage import get_user_conversation_messages
    msgs = get_user_conversation_messages(user_id, character_id)
    return [{"role": m["role"], "content": m["content"],
             "timestamp": str(m["timestamp"]) if m.get("timestamp") else None} for m in msgs]

class AdminDmRequest(BaseModel):
    content: str

@app.post("/admin/users/{user_id}/dm")
async def admin_send_dm(user_id: str, request: Request, body: AdminDmRequest, user: AuthUser = Depends(admin_required)):
    if not body.content.strip():
        raise HTTPException(400, "Messaggio vuoto")
    from storage import send_admin_dm, audit_log
    dm = send_admin_dm(user.user_id, user_id, body.content.strip())
    audit_log(user.user_id, "admin.send_dm", f"to={user_id} len={len(body.content)}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "id": dm["id"], "created_at": str(dm["created_at"])}

@app.get("/admin/users/{user_id}/dms")
async def admin_list_dms(user_id: str, user: AuthUser = Depends(admin_required)):
    from storage import list_admin_dms
    return list_admin_dms(user_id)

@app.post("/admin/users/{user_id}/dms/read")
async def admin_mark_dms_read(user_id: str, user: AuthUser = Depends(admin_required)):
    from storage import mark_admin_dms_read
    count = mark_admin_dms_read(user_id)
    return {"marked_read": count}

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Group Chats
# ═══════════════════════════════════════════════════════════════════

@app.get("/group-chats")
async def list_group_chats(user: AuthUser = Depends(jwt_required)):
    from storage import list_group_chats as _lgc
    return _lgc(user.user_id)

@app.post("/group-chats")
async def create_group_chat(request: Request, body: CreateGroupChatRequest, user: AuthUser = Depends(jwt_required)):
    name = body.name.strip()
    character_ids = body.character_ids
    if not name:
        raise HTTPException(400, "Nome chat richiesto")
    if not character_ids or len(character_ids) < 2:
        raise HTTPException(400, "Servono almeno 2 personaggi per una chat di gruppo")
    if len(character_ids) > 8:
        raise HTTPException(400, "Massimo 8 personaggi per chat di gruppo")
    from storage import create_group_chat as _cgc, audit_log
    chat = _cgc(user.user_id, name, character_ids)
    audit_log(user.user_id, "group_chat.create", f"name={name} chars={len(character_ids)}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return chat

@app.get("/group-chats/{chat_id}")
async def get_group_chat(chat_id: int, user: AuthUser = Depends(jwt_required)):
    from storage import get_group_chat as _ggc, get_group_messages as _ggm
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    messages = _ggm(chat_id, limit=100)
    chat["messages"] = messages
    return chat

@app.delete("/group-chats/{chat_id}")
async def delete_group_chat(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    from storage import get_group_chat as _ggc, delete_group_chat as _dgc, audit_log
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    _dgc(chat_id)
    audit_log(user.user_id, "group_chat.delete", f"chat={chat_id} name={chat['name']}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "deleted": chat_id}

@app.post("/group-chats/{chat_id}/message")
async def send_group_message(chat_id: int, request: Request, user: AuthUser = Depends(jwt_required)):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Messaggio vuoto")
    from storage import get_group_chat as _ggc, add_group_message as _agm
    from characters import get_character
    chat = _ggc(chat_id, user.user_id)
    if not chat:
        raise HTTPException(404, "Chat di gruppo non trovata")
    _agm(chat_id, "user", user.user_id, "user", text)
    characters = []
    for cid in chat["character_ids"]:
        c = get_character(cid)
        if c:
            characters.append(c)
    if not characters:
        raise HTTPException(400, "Nessun personaggio valido trovato")
    from storage import get_group_messages as _ggm
    history = _ggm(chat_id, limit=50)

    responses = []
    previous_responses = []

    for char in characters:
        from prompt_builder import build_group_messages
        messages = build_group_messages(
            characters, text, history=history,
            username=user.user_id[:8],
            current_character=char["name"],
            previous_responses=previous_responses
        )
        from ai_engine import get_ai_response_stream
        full_response = ""
        for token_data in get_ai_response_stream(messages, user_id=user.user_id):
            if isinstance(token_data, tuple):
                token = token_data[0]
            else:
                token = token_data
            full_response += token

        reply = full_response.strip()
        if reply:
            _agm(chat_id, "character", char["id"], "assistant", reply)
            responses.append({"character_id": char["id"],
                              "character_name": char["name"],
                              "content": reply})
            previous_responses.append({"name": char["name"], "content": reply})

    return {"responses": responses, "user_message": text}

# ═══════════════════════════════════════════════════════════════════
# ROUTES: Chat & Media
# ═══════════════════════════════════════════════════════════════════
@app.post("/chat")
@limiter.limit("60/minute")
async def api_chat(request: Request, body: ChatRequest, user: AuthUser = Depends(jwt_required)):
    character_id = body.character or list_characters()[0]["id"]
    text = body.text
    username = body.username

    client_state = {
        "relationship": body.relationship_state,
        "personality": body.personality_state,
        "evolution": body.evolution_state,
        "shifts": body.shifts,
        "summaries": body.summaries,
    }

    if not text and not body.image:
        raise HTTPException(400, "text or image required")
    if text:
        ok, msg = security_utils.nsfw_check_text(text)
        if not ok:
            raise HTTPException(400, msg)

    char = get_character(character_id)
    if char and not _check_character_access(user.user_id, char):
        raise HTTPException(403, "premium_required")

    result = process_message(user.user_id, character_id, text, username,
                             memory_context=body.memory_context,
                             user_memory=body.user_memory,
                             character_data=body.character_data,
                             image_base64=body.image,
                             image_mime=body.image_mime,
                             client_storage=body.client_storage,
                             client_state=client_state,
                             is_favorite=body.is_favorite)
    if not result:
        raise HTTPException(404, "character not found")

    resp = {
        "response": result["ai_text"],
        "emotion": result["emotion"],
        "emotion_intensity": result["intensity"],
        "ai_provider": result.get("ai_provider", ""),
        "ai_model": result.get("ai_model", ""),
        "character_id": character_id,
        "character_name": result["character"]["name"],
    }
    mem_updates = result.get("memory_updates", {})
    if mem_updates:
        resp["memory_updates"] = mem_updates
    evo_updates = result.get("evo_updates", {})
    if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
        resp["evo_updates"] = evo_updates
    if body.client_storage:
        cs = result.get("client_state", {})
        if cs:
            resp["client_state"] = cs
    return resp

@app.post("/transcribe")
@limiter.limit("10/minute")
async def api_transcribe(request: Request, audio: UploadFile = File(...), user: AuthUser = Depends(jwt_required)):
    if not audio.filename or audio.filename.strip() == "":
        raise HTTPException(400, "audio file required")
    if not audio_utils.allowed_audio_file(audio.filename):
        raise HTTPException(400, "formato audio non supportato")

    content = await audio.read()
    import tempfile
    path = tempfile.mktemp(suffix=os.path.splitext(audio.filename)[1])
    with open(path, "wb") as f:
        f.write(content)

    ok, msg = security_utils.validate_file_mime(path, os.path.splitext(audio.filename)[1])
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"⚠️ File infetto rilevato — user={user.user_id} detail={msg}")
        raise HTTPException(400, msg)

    ok, msg = security_utils.validate_audio_duration(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.validate_audio_sample_rate(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    text = audio_utils.transcribe_audio(path)
    try: os.remove(path)
    except Exception: pass
    if not text:
        raise HTTPException(500, detail="transcription failed")
    return {"text": text}

@app.post("/tts")
async def api_tts(body: TtsRequest, user: AuthUser = Depends(jwt_required)):
    if not body.text:
        raise HTTPException(400, "text required")
    if not is_content_unlocked(user.user_id, "feature", "premium_voice"):
        raise HTTPException(403, "premium_voice_required")
    char = get_character(body.character_id) if body.character_id else None
    voice_profile = audio_utils.get_voice_profile(char) if char else {"model": "it_IT-riccardo-medium", "speed": 1.0, "pitch": 1.0}
    output_path = audio_utils.text_to_speech(body.text, voice_profile)
    if not output_path:
        raise HTTPException(500, "TTS generation failed")

    def generate():
        with open(output_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk
        try: os.remove(output_path)
        except Exception: pass

    return StreamingResponse(generate(), media_type="audio/wav",
                             headers={"Content-Disposition": "inline; filename=response.wav"})

@app.post("/upload-image")
@limiter.limit("10/minute")
async def api_upload_image(request: Request, image: UploadFile = File(...), user: AuthUser = Depends(jwt_required)):
    if not image.filename or image.filename.strip() == "":
        raise HTTPException(400, "image file required")
    if not image_utils.validate_image(image.filename):
        raise HTTPException(400, "invalid image format (jpg/png/webp only)")

    content = await image.read()
    if len(content) > image_utils.MAX_IMAGE_SIZE:
        raise HTTPException(400, "image too large (max 10MB)")

    import tempfile
    ext = os.path.splitext(image.filename)[1]
    path = tempfile.mktemp(suffix=ext)
    with open(path, "wb") as f:
        f.write(content)

    ok, msg = security_utils.validate_file_mime(path, ext)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        raise HTTPException(400, msg)

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"⚠️ Immagine infetta rilevata — user={user.user_id} detail={msg}")
        raise HTTPException(400, msg)

    ok, msg = security_utils.nsfw_check_image(path)
    if not ok:
        from storage import flag_user
        flag_user(user.user_id, f"NSFW image: {msg}", "image", msg, "high")
        try: os.remove(path)
        except Exception: pass
        _send_alert(f"🔞 NSFW rilevato — user={user.user_id} reason={msg}")
        raise HTTPException(400, "Contenuto non appropriato")

    security_utils.strip_exif(path)
    path = image_utils.resize_image(path)
    b64 = image_utils.image_to_base64(path)
    mime = security_utils.EXT_TO_MIME.get(ext, "image/jpeg")
    try: os.remove(path)
    except Exception: pass
    return {"base64": b64, "mime": mime}

@app.get("/static/videos/{filename}")
async def api_video(filename: str):
    import re as _re
    if not _re.match(r"^[a-f0-9]{32}\.mp4$", filename):
        raise HTTPException(400, "invalid")
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "videos", filename)
    if not os.path.isfile(video_path):
        raise HTTPException(404, "not found")
    return FileResponse(video_path, media_type="video/mp4")

# ═══════════════════════════════════════════════════════════════════
# CORE LOGIC: process_message (unchanged from server.py)
# ═══════════════════════════════════════════════════════════════════
def _check_character_access(user_id, character):
    if not user_id:
        return False
    category_id = character.get("category", "")
    for cat in get_categories():
        if cat["id"] == category_id:
            mvc_cost = cat.get("mvc_cost", 0)
            if mvc_cost > 0 and not is_content_unlocked(user_id, "category", category_id):
                return False
            break
    return True

def process_message(user_id, character_id, text, username="Utente",
                    memory_context=None, user_memory=None,
                    character_data=None, image_base64="", image_mime="image/jpeg",
                    client_storage=False, client_state=None, is_favorite=False):
    client_state = client_state or {}
    character = get_character(character_id)
    if character_data:
        if isinstance(character_data, str):
            character_data = json.loads(character_data)
        character = character_data
    if not character:
        return None
    if not _check_character_access(user_id, character):
        return None

    def _check_cooldown():
        now = time.time()
        last = MEDIA_COOLDOWNS.get(user_id, 0)
        remaining = MEDIA_COOLDOWN_SECONDS - (now - last)
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            return f"⏳ Devi aspettare {mins}m {secs}s prima di generare altro contenuto."
        return None

    GEN_PREFIX = "/genera"
    MOVE_PREFIX = "/muovi"

    stripped = text.strip()
    if stripped.startswith(GEN_PREFIX) or stripped.startswith(MOVE_PREFIX):
        is_video = stripped.startswith(MOVE_PREFIX)
        feature_id = "video_gen" if is_video else "image_gen"
        if not is_content_unlocked(user_id, "feature", feature_id):
            feat = FEATURES[feature_id]
            return {
                "ai_text": f"🔒 Per usare {feat['name']} serve sbloccare la funzionalità ({feat['mvc_cost']} MVC). Vai nella sezione Guadagna MVC.",
                "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "neutro", "intensity": 0.0,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }
        cooldown_msg = _check_cooldown()
        if cooldown_msg:
            return {
                "ai_text": cooldown_msg, "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "neutro", "intensity": 0.0,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }

        prefix_len = len(MOVE_PREFIX) if is_video else len(GEN_PREFIX)
        prompt = stripped[prefix_len:].strip()
        if not prompt:
            prompt = f"Ritratto fotorealistico di {character.get('name', 'una persona')}, {character.get('description', '')}"
        else:
            prompt = f"Photorealistic portrait of {prompt}, cinematic lighting, detailed face, natural skin texture, 4K"

        now = time.time()
        if is_video:
            video_url, image_b64 = _generate_chat_video(prompt)
            if video_url:
                MEDIA_COOLDOWNS[user_id] = now
                return {
                    "ai_text": "🎬 Video animato generato con SadTalker!",
                    "ai_provider": "flux+sadtalker", "ai_model": "FLUX.1-schnell+SadTalker",
                    "is_fallback": False, "emotion": "felice", "intensity": 0.5,
                    "character": character, "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                    "generated_image": image_b64, "generated_video": video_url,
                }
            else:
                image_b64 = _generate_chat_image(prompt)
                if image_b64:
                    MEDIA_COOLDOWNS[user_id] = now
                    return {
                        "ai_text": "⚠️ Animazione non riuscita, ma ecco l'immagine generata.",
                        "ai_provider": "flux", "ai_model": "FLUX.1-schnell",
                        "is_fallback": False, "emotion": "neutro", "intensity": 0.3,
                        "character": character, "memory_updates": None,
                        "evo_updates": {"new_stage": None, "unlocked": []},
                        "generated_image": image_b64,
                    }
                return {
                    "ai_text": "❌ Errore nella generazione. Riprova più tardi.",
                    "ai_provider": "system", "ai_model": "",
                    "is_fallback": False, "emotion": "triste", "intensity": 0.3,
                    "character": character, "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                }

        image_b64 = _generate_chat_image(prompt)
        if image_b64:
            MEDIA_COOLDOWNS[user_id] = now
            return {
                "ai_text": "✨ Ecco l'immagine generata con FLUX.1-schnell!",
                "ai_provider": "flux", "ai_model": "FLUX.1-schnell",
                "is_fallback": False, "emotion": "felice", "intensity": 0.5,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
                "generated_image": image_b64,
            }
        else:
            return {
                "ai_text": "❌ Errore nella generazione dell'immagine. Riprova più tardi.",
                "ai_provider": "system", "ai_model": "",
                "is_fallback": False, "emotion": "triste", "intensity": 0.3,
                "character": character, "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }

    image_desc = None
    if image_base64:
        image_desc = image_utils.describe_image(image_base64, image_mime)
        if image_desc:
            text = (text + "\n\n[IMAGE: " + image_desc + "]") if text else "[IMAGE: " + image_desc + "]"

    emotion, intensity, emotions = detect_emotion(text)

    if client_storage:
        relationship = client_state.get("relationship", get_relationship(user_id, character_id))
        personality = client_state.get("personality", get_personality(character_id, character.get("core_traits", {})))
        history = memory_context if memory_context is not None else client_state.get("history", [])
        shifts = client_state.get("shifts", [])
        evo = client_state.get("evolution", get_evolution(user_id, character_id))
        summaries = client_state.get("summaries", [])
    else:
        relationship = get_relationship(user_id, character_id)
        # Phase 2: Use per-user personality (falls back to shared if not yet personalized)
        personality = get_user_personality(user_id, character_id, character.get("core_traits", {}))
        _msg_limit = 50 if is_content_unlocked(user_id, "feature", "extended_memory") else 20
        history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=_msg_limit)
        shifts = get_recent_shifts(user_id, character_id)
        evo = get_evolution(user_id, character_id)
        summaries = get_memories(user_id, character_id, limit=5)

    # Phase 2: Per-user world state
    if client_storage:
        world_state = get_world_state()
    else:
        world_state = get_user_world_state(user_id)
    user_prefs = get_user_preferences(user_id)
    user_gender = user_prefs.get("user_gender") or None
    user_age = user_prefs.get("user_age") or None
    sexual_orientation = user_prefs.get("sexual_orientation") or None

    if not client_storage:
        is_first = count_all_user_messages(user_id) == 0
        add_message(user_id, character_id, "user", text)
        if is_first:
            credit_referral_first_message(user_id)
        # Phase 5: Track conversation session
        start_conversation_session(user_id, character_id)
        # Phase 8: Track conversation topics
        update_conversation_topics(user_id, character_id, text)

    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)

    if not client_storage:
        if evo_updates["relationship_deltas"]:
            update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
        reward = evo_updates.get("mevacoins_reward", 0)
        if reward:
            add_mevacoins(user_id, reward, f"milestone:{character_id}")
        if evo_updates["trait_modifiers"]:
            # Phase 2: Update per-user personality
            update_user_personality_db(user_id, character_id, evo_updates["trait_modifiers"])
        if not character.get("evolution"):
            rel_deltas = _compute_relationship_deltas(emotion, intensity)
            if any(v != 0 for v in rel_deltas.values()):
                update_relationship(user_id, character_id, rel_deltas)
            pers_deltas = _compute_personality_deltas(emotion, intensity, relationship)
            if any(v != 0 for v in pers_deltas.values()):
                # Phase 2: Update per-user personality
                update_user_personality_db(user_id, character_id, pers_deltas)
        update_evolution(user_id, character_id, evo)

    learned = evo.setdefault("learned", {"topics": [], "personality_drift": {}, "new_skills": []})
    knowledge = character.get("knowledge_domains", {})
    ignorance_list = knowledge.get("ignorance", [])
    text_lower = text.lower()

    is_blank = character.get("id") == "blank" or (
        not character.get("full_name") and
        not character.get("knowledge_domains", {}).get("expertise") and
        not character.get("knowledge_domains", {}).get("familiarity")
    )
    if is_blank:
        teaching_patterns = [
            "ti insegno", "ti spiego", "il che significa", "in pratica",
            "come funziona", "la regola è", "devi sapere", "è importante",
            "impara che", "sappi che", "cos'è", "significa che",
            "per esempio", "in altre parole", "in sintesi",
        ]
        teaching_detected = any(p in text_lower for p in teaching_patterns)
        topic_indicators = [
            "la musica è", "la scienza è", "la storia è", "la matematica",
            "il computing", "la programmazione", "la cucina è", "lo sport",
            "l'arte è", "la filosofia", "la letteratura", "la medicina",
        ]
        topic_detected = any(t in text_lower for t in topic_indicators)
        if teaching_detected or topic_detected:
            topic_label = _extract_teaching_topic(text)
            if topic_label and topic_label not in learned.get("topics", []):
                learned.setdefault("topics", []).append(topic_label)
                learned.setdefault("new_skills", []).append(topic_label)
                if topic_label not in knowledge.get("expertise", []):
                    knowledge.setdefault("expertise", []).append(topic_label)
                    character["knowledge_domains"] = knowledge
        personality_labels = {
            "joy": "allegro", "romance": "affettuoso", "challenge": "curioso",
            "sadness": "empatico", "anger": "passionale",
        }
        p_label = personality_labels.get(emotion)
        if p_label:
            learned.setdefault("personality_drift", {})
            current = learned["personality_drift"].get(p_label, 0.0)
            learned["personality_drift"][p_label] = round(min(3.0, current + 0.05), 2)

    for topic in ignorance_list:
        if not isinstance(topic, str):
            continue
        keywords = [w for w in topic.lower().split() if len(w) > 3]
        if not keywords:
            keywords = [topic.lower()]
        matched = sum(1 for kw in keywords if kw in text_lower)
        if matched >= 1 and matched >= len(keywords) * 0.5:
            topic_key = f"teaching:{topic}"
            evo["flags"][topic_key] = evo["flags"].get(topic_key, 0) + 1
            if evo["flags"][topic_key] >= 3 and topic not in learned["topics"]:
                learned["topics"].append(topic)

    emotion_drift = {
        "joy": {"warmth": 0.02, "playfulness": 0.03},
        "anger": {"warmth": -0.03, "strictness": 0.02, "sarcasm": 0.03},
        "romance": {"warmth": 0.03, "playfulness": 0.02},
        "sadness": {"warmth": 0.01, "patience": 0.02},
        "challenge": {"strictness": 0.02, "sarcasm": 0.03},
    }
    drift = emotion_drift.get(emotion, {})
    for trait, delta in drift.items():
        current = learned["personality_drift"].get(trait, 0.0)
        clamped = max(-3.0, min(3.0, current + delta))
        learned["personality_drift"][trait] = round(clamped, 2)

    if not client_storage:
        update_evolution(user_id, character_id, evo)

    new_name = _detect_character_rename(text)
    if new_name:
        evo["flags"]["custom_name"] = new_name
        if not client_storage:
            update_evolution(user_id, character_id, evo)

    if evo.get("flags", {}).get("custom_name"):
        character = {**character, "name": evo["flags"]["custom_name"]}

    memory_updates = _extract_memory_updates(user_id, text, character, character_id)
    if not client_storage:
        if memory_updates:
            wrapped = {}
            for key, val in memory_updates.items():
                wrapped[key] = {"value": val, "source": character_id, "source_name": character["name"]}
            # Phase 3: Use enhanced memory update with importance scoring
            update_user_memory_enhanced(user_id, wrapped, source_character=character_id, source_name=character["name"])
            # Phase 7: Share important facts across all characters
            for key, val in memory_updates.items():
                val_str = val if isinstance(val, str) else val.get("value", str(val)) if isinstance(val, dict) else str(val)
                if len(val_str) > 3:
                    share_memory_across_characters(user_id, key, val_str, character_id, character["name"])
        # Phase 3: Apply temporal decay (run periodically, cheap check)
        import random
        if random.random() < 0.05:  # 5% chance per message
            try:
                decay_user_memory(user_id)
            except Exception as e:
                logger.warning(f"Memory decay failed: {e}")
        stored = get_user_memory(user_id).get("memory", {})
        if stored:
            # Phase 3: Get most relevant memories, not all
            user_memory = stored

    evo["dialog_hints"] = evo_updates.get("dialog_hints", [])
    evo["_just_unlocked"] = evo_updates.get("unlocked", [])

    _total_msgs = count_messages(user_id, character_id)

    # Phase 5: Get temporal context for prompt
    temporal_context = {}
    recent_topics = []
    shared_mems = []
    if not client_storage:
        try:
            temporal_context = get_temporal_context(user_id, character_id)
            recent_topics = get_recent_topics(user_id, character_id, days=7, limit=5)
            shared_mems = get_shared_memories(user_id, limit=5)
        except Exception as e:
            logger.warning(f"Memory context failed: {e}")

    messages = build_messages(
        character, {"emotion": emotion, "intensity": intensity},
        relationship, personality, world_state, text, user_id, history,
        shifts, username, user_memory=user_memory, summaries=summaries,
        evolution=evo, is_favorite=is_favorite, total_messages=_total_msgs,
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
        temporal_context=temporal_context, recent_topics=recent_topics,
        shared_memories=shared_mems,
    )

    ai_text, ai_provider, ai_model = get_ai_response(messages, user_id=user_id)
    if not ai_text:
        ai_text = _fallback_response(character, emotion)
        ai_provider = "fallback"
        ai_model = ""
        is_fallback = True
    else:
        is_fallback = False

    if not is_fallback and not client_storage:
        add_message(user_id, character_id, "assistant", ai_text)

    if not client_storage:
        try:
            _maybe_summarize(user_id, character_id, character)
        except Exception as e:
            logger.warning(f"Summarize failed: {e}")

    result = {
        "ai_text": ai_text, "ai_provider": ai_provider, "ai_model": ai_model,
        "is_fallback": is_fallback, "emotion": emotion, "intensity": intensity,
        "character": character, "memory_updates": memory_updates,
        "evo_updates": {"new_stage": evo_updates.get("new_stage"), "unlocked": evo_updates.get("unlocked", [])},
    }

    if client_storage:
        if evo_updates.get("relationship_deltas"):
            for k, v in evo_updates["relationship_deltas"].items():
                relationship[k] = max(0, min(100, relationship.get(k, 0) + v))
        if evo_updates.get("trait_modifiers"):
            for trait, delta in evo_updates["trait_modifiers"].items():
                personality[trait] = max(0, min(10, personality.get(trait, 5) + delta))
        result["client_state"] = {
            "relationship": relationship, "personality": personality,
            "evolution": evo, "shifts": shifts, "summaries": summaries,
            "memory_updates": memory_updates,
            "learned": evo.get("learned", {"topics": [], "personality_drift": {}, "new_skills": []}),
        }

    return result

# ═══════════════════════════════════════════════════════════════════
# HELPERS (unchanged)
# ═══════════════════════════════════════════════════════════════════
def _compute_relationship_deltas(emotion, intensity):
    deltas = {"trust": 0, "affinity": 0, "respect": 0, "conflict": 0}
    d = round(intensity * 2)
    if emotion == "anger":
        deltas.update({"conflict": d, "trust": -d, "affinity": -d})
    elif emotion == "romance":
        deltas.update({"affinity": d, "trust": round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"respect": d, "trust": round(d * 0.3)})
    elif emotion == "joy":
        deltas.update({"affinity": round(d * 0.5), "trust": round(d * 0.3)})
    elif emotion == "sadness":
        deltas.update({"trust": round(d * 0.5), "affinity": round(d * 0.3)})
    elif emotion == "fear":
        deltas["trust"] = round(d * 0.7)
    return deltas

def _compute_personality_deltas(emotion, intensity, relationship):
    deltas = {"warmth": 0, "strictness": 0, "patience": 0, "sarcasm": 0}
    d = round(intensity)
    if emotion == "anger":
        deltas.update({"patience": -d, "strictness": d, "sarcasm": round(d * 0.5)})
    elif emotion == "romance":
        deltas.update({"warmth": d, "sarcasm": -round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"strictness": round(d * 0.5), "sarcasm": d})
    elif relationship.get("conflict", 0) > 50:
        deltas.update({"patience": -1, "sarcasm": 1})
    elif relationship.get("affinity", 0) > 50:
        deltas.update({"warmth": 1, "patience": 1})
    return deltas

def _fallback_response(character, emotion):
    name = character["name"]
    fb = {
        "anger": f"{name} incrocia le braccia. «Calma. Raccontami cosa c'è che non va.»",
        "romance": f"{name} sorride. «Sei molto gentile.»",
        "challenge": f"{name} alza un sopracciglio. «Una sfida? Mi piace.»",
        "sadness": f"{name} ti guarda con comprensione. «Se vuoi parlare, io sono qui.»",
        "fear": f"{name} si avvicina. «Tranquillo, sono qui con te.»",
        "joy": f"{name} ride. «Che bello vederti di buon umore!»",
    }
    return fb.get(emotion, f"{name} annuisce. «Raccontami di più.»")

def _maybe_summarize(user_id, character_id, character):
    total = count_messages(user_id, character_id)
    checkpoint = get_last_summary_checkpoint(user_id, character_id)
    if total - checkpoint < SUMMARY_INTERVAL:
        return
    old = get_recent_messages(user_id, character_id, limit=SUMMARY_INTERVAL)
    if len(old) < 3:
        return
    text = ""
    for m in old[-15:]:
        role = "Utente" if m["role"] == "user" else character["name"]
        text += f"{role}: {m['content']}\n"
    prev_summaries = get_memories(user_id, character_id, limit=3)
    prev_text = ""
    if prev_summaries:
        for s in prev_summaries:
            prev_text += f"- {s.get('summary', '')}\n"
    prompt = (
        f"Sei un assistente che riassume conversazioni tra un utente e {character['name']}.\n"
        f"Estrai informazioni personali sull'utente (nome, soprannome, hobby, lavoro, gusti, preferenze, ecc.) "
        f"e includile nel riassunto.\n\n"
    )
    if prev_text:
        prompt += f"Riassunti precedenti:\n{prev_text}\n\n"
    prompt += (
        f"Conversazione recente:\n{text}\n\n"
        "Scrivi un riassunto dettagliato in 3-4 frasi, includendo eventuali nuovi dettagli sull'utente."
    )
    summary, _, _ = get_ai_response([
        {"role": "system", "content": "Sei un assistente che riassume conversazioni in italiano."},
        {"role": "user", "content": prompt}
    ], user_id=user_id)
    if not summary:
        return
    rel = get_relationship(user_id, character_id)
    topics = []
    user_mem = get_user_memory(user_id).get("memory", {})
    if user_mem:
        topics = list(user_mem.keys())
    add_memory(user_id, character_id, summary, topics, total,
        {"trust": rel.get("trust", 0), "affinity": rel.get("affinity", 0), "intimacy": rel.get("intimacy", 0)})

_MEMORY_KEYWORDS = [
    "mi piace", "mi piacciono", "sono", "ho ", "voglio", "vorrei",
    "preferisco", "odio", "amo", "faccio", "lavoro", "studio",
    "vivo", "abit", "mi chiamo", "il mio", "la mia", "i miei",
    "le mie", "detesto", "adoro", "non mi piace",
    "mi piace tanto", "mi fa impazzire", "il mio preferito", "la mia passione", "mi diverto",
]

_RENAME_PATTERNS = [
    r"ti\s+chiamerai\s+(\w+)", r"ti\s+chiamo\s+(\w+)", r"ti\s+chiami\s+(\w+)",
    r"il\s+tuo\s+nome\s+(?:è|sarà|sara)\s+(\w+)", r"ti\s+chiamerò\s+(\w+)",
    r"il\s+nome\s+(?:è|sarà|sara)\s+(\w+)",
]

def _detect_character_rename(user_text):
    text_lower = user_text.lower()
    for pattern in _RENAME_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            name = m.group(1).strip().capitalize()
            if len(name) >= 2:
                return name
    return None

def _extract_teaching_topic(user_text):
    text_lower = user_text.lower()
    topic_keywords = {
        "musica": ["musica", "canzone", "chitarra", "pianoforte", "batteria", "cantare", "suonare", "nota", "melodia"],
        "cucina": ["cucina", "ricetta", "cibo", "dolce", "pasta", "cuocere", "ingrediente", "piatto"],
        "tecnologia": ["computer", "programmazione", "tecnologia", "codice", "software", "hardware", "internet", "app"],
        "storia": ["storia", "passato", "antico", "guerra", "re", "impero", "medievale", "romano"],
        "scienza": ["scienza", "fisica", "chimica", "biologia", "matematica", "formula", "esperimento"],
        "arte": ["arte", "dipinto", "scultura", "museo", "colore", "pennello", "artistico"],
        "sport": ["sport", "palestra", "allenamento", "correre", "nuoto", "calcio", "basket"],
        "moda": ["moda", "vestito", "stile", "abbigliamento", "trend", "elegante"],
        "viaggi": ["viaggio", "turismo", "meta", "vacanza", "esplorare", "paese", "città"],
        "filosofia": ["filosofia", "pensiero", "esistenza", "senso", "verità", "morale"],
        "medicina": ["medicina", "salute", "dottore", "farmaco", "malattia", "corpo"],
        "natura": ["natura", "pianta", "animale", "foresta", "montagna", "mare"],
        "lingue": ["lingua", "parlare", "inglese", "spagnolo", "francese", "tradurre"],
        "economia": ["economia", "denaro", "investimento", "business", "mercato"],
        "religione": ["religione", "fede", "preghiera", "spirito", "credere"],
    }
    best_topic, best_score = None, 0
    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_topic = topic
    if best_score >= 1:
        return best_topic
    words = text_lower.split()
    for w in words:
        if len(w) > 4 and w not in {"questo", "quello", "essere", "avere", "fare", "dire", "cosa", "come", "perché", "perche", "quando", "dove", "chi"}:
            return w
    return None

def _mentions_personal_info(text):
    """Gatekeeper: returns True only if the message likely contains personal info worth extracting."""
    text_lower = text.lower()
    # Direct personal statements
    direct = any(kw in text_lower for kw in _MEMORY_KEYWORDS)
    if direct:
        return True
    # Broader patterns: "io sono", "a me piace", "il mio lavoro", etc.
    broad_patterns = [
        "io sono", "a me ", "per me ", "il mio ", "la mia ", "i miei ", "le mie ",
        "mi chiamo", "ho bisogno", "vivo a", "abito a", "studio a", "lavoro a",
        "mi piace", "mi piaceva", "adoro ", "detesto ", "odio ",
        "sono di ", "vengo da", "parlo ", "conosco ",
    ]
    return any(p in text_lower for p in broad_patterns)

def _extract_user_facts(user_id, user_text, character_name):
    """Extract personal facts from user message via LLM. Called only when _mentions_personal_info() is True."""
    prompt = (
        f"L'utente ha detto a {character_name}: \"{user_text}\"\n\n"
        "Estrai eventuali informazioni personali sull'utente e restituiscile come JSON con chiavi in italiano. "
        "Ogni valore deve essere una stringa concisa. Se non ci sono informazioni personali, restituisci solo {}.\n"
        "Esempio: {\"hobby\": \"gioca a pallone\", \"lavoro\": \"insegnante\"}\n"
        "Restituisci SOLO il JSON, nient'altro."
    )
    msgs = [
        {"role": "system", "content": "Sei un assistente che estrae informazioni personali in formato JSON."},
        {"role": "user", "content": prompt},
    ]
    result, _, _ = get_ai_response(msgs, user_id=user_id)
    if not result:
        return {}
    json_match = re.search(r'\{.*\}', result, re.DOTALL)
    if not json_match:
        return {}
    try:
        return json.loads(json_match.group(0))
    except Exception:
        return {}

def _extract_memory_updates(user_id, user_text, character, character_id=None):
    """Phase 1: Only call LLM extraction if message likely contains personal info."""
    if not _mentions_personal_info(user_text):
        return {}
    return _extract_user_facts(user_id, user_text, character["name"])

# ─── Image/Video generation ──────────────────────────────────────
def _get_hf_token():
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hf_token")
        if os.path.isfile(token_file):
            token = open(token_file).read().strip()
    return token

def _generate_chat_image(prompt):
    token = _get_hf_token()
    if not token:
        return None
    try:
        import requests as _req
        resp = _req.post(
            _CHAT_GEN_API_URL + _CHAT_GEN_MODEL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": "cartoon, anime, illustration, low quality, blurry, distorted face, bad anatomy",
                    "guidance_scale": 7.5,
                    "num_inference_steps": 4
                }
            },
            timeout=120
        )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
        return None
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        return None

def _generate_chat_video(prompt):
    image_b64 = _generate_chat_image(prompt)
    if not image_b64:
        return None, None
    import tempfile
    import shutil
    import wave
    img_path = None
    audio_path = None
    try:
        img_data = base64.b64decode(image_b64)
        img_path = tempfile.mktemp(suffix=".png")
        with open(img_path, "wb") as f:
            f.write(img_data)
        tts_text = prompt[:150] if prompt else "Ciao, sono un avatar animato."
        try:
            from gtts import gTTS
            audio_path = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=tts_text, lang="it")
            tts.save(audio_path)
        except Exception:
            audio_path = tempfile.mktemp(suffix=".wav")
            with wave.open(audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * 22050)
        from gradio_client import Client
        client = Client("John6666/SadTalker")
        result = client.predict(
            img_path, audio_path, "crop", True, True, 2, 256, 0,
            "facevid2vid", 1.0, False, None, "pose", False, 5, True,
            api_name="/test"
        )
        video_url = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")
            if video_path:
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                video_dir = os.path.join(backend_dir, "static", "videos")
                os.makedirs(video_dir, exist_ok=True)
                video_filename = f"{uuid.uuid4().hex}.mp4"
                dest = os.path.join(video_dir, video_filename)
                shutil.copy2(video_path, dest)
                video_url = f"/static/videos/{video_filename}"
        return video_url, image_b64
    except Exception as e:
        logger.error(f"Video gen error: {e}")
        return None, None
    finally:
        for p in [img_path, audio_path]:
            try:
                if p and os.path.isfile(p):
                    os.unlink(p)
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════════════
# Socket.IO HANDLERS
# ═══════════════════════════════════════════════════════════════════
@sio.event
async def connect(sid, environ, auth):
    token = None
    user_id = None
    role = "user"
    if auth and isinstance(auth, dict):
        token = auth.get("token", "")
    if token and token != "local_session":
        payload = socket_authenticate(token)
        if payload:
            user_id = payload["user_id"]
            role = payload.get("role", "user")
    if not user_id:
        user_id = "anon_" + uuid.uuid4().hex[:12]
    socket_auth_map[sid] = {"user_id": user_id, "role": role}
    user_sessions[user_id] = sid

@sio.event
async def disconnect(sid):
    socket_auth_map.pop(sid, None)
    for uid, _sid in list(user_sessions.items()):
        if _sid == sid:
            del user_sessions[uid]
            break
    user_names.pop(sid, None)
    user_rooms.pop(sid, None)

@sio.on("add user")
async def on_add_user(sid, data):
    auth_data = socket_auth_map.get(sid)
    if not auth_data:
        await sio.emit("error", {"message": "Non autenticato"}, room=sid)
        return
    user_id = auth_data["user_id"]
    username = data.get("username", "Utente")
    character_id = data.get("character", list_characters()[0]["id"])
    user_rooms[sid] = user_id
    user_names[sid] = username
    character = get_character(character_id)
    character_name = character["name"] if character else "AI"
    await sio.enter_room(sid, user_id)
    await sio.emit("login", {
        "numUsers": len(user_sessions),
        "username": username,
        "user_id": user_id,
        "character_id": character_id,
        "character_name": character_name
    }, room=sid)
    greet_key = (user_id, character_id)
    if greet_key in greeted_users:
        return
    greeted_users.add(greet_key)

    total_msgs = count_messages(user_id, character_id)

    if total_msgs == 0:
        greeting = _generate_greeting(character, character_name, username, user_id=user_id)
        add_message(user_id, character_id, "assistant", greeting)
        await sio.emit("new message", {
            "username": character_name, "message": greeting, "is_roleplay": True
        }, room=sid)

@sio.on("new message")
async def on_new_message(sid, data):
    user_id = user_rooms.get(sid)
    if not user_id:
        await sio.emit("error", {"message": "Not logged in"}, room=sid)
        return
    text = data.get("message", "")
    character_id = data.get("character", list_characters()[0]["id"])
    image_b64 = data.get("image", "")
    image_mime = data.get("image_mime", "image/jpeg")
    if not text and not image_b64:
        return
    if text:
        ok, msg = security_utils.nsfw_check_text(text)
        if not ok:
            await sio.emit("error", {"message": msg}, room=sid)
            return
    username = user_names.get(sid, "Utente")
    result = process_message(user_id, character_id, text, username,
                             memory_context=data.get("memory_context"),
                             user_memory=data.get("user_memory"),
                             character_data=data.get("character_data"),
                             image_base64=image_b64, image_mime=image_mime,
                             is_favorite=data.get("is_favorite", False))
    if not result:
        await sio.emit("error", {"message": "Character not found"}, room=sid)
        return
    await sio.emit("new message", {
        "username": username, "message": text, "is_roleplay": False
    }, room=sid)
    mem_updates = result.get("memory_updates", {})
    evo_updates = result.get("evo_updates", {})
    response_data = {
        "username": result["character"]["name"],
        "message": result["ai_text"],
        "emotion": result["emotion"],
        "ai_provider": result.get("ai_provider", ""),
        "ai_model": result.get("ai_model", ""),
        "is_roleplay": True,
        "is_fallback": result.get("is_fallback", False),
    }
    if mem_updates:
        response_data["memory_updates"] = mem_updates
    if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
        response_data["evo_updates"] = evo_updates
    if result.get("generated_image"):
        response_data["generated_image"] = result["generated_image"]
    if result.get("generated_video"):
        response_data["generated_video"] = result["generated_video"]
    await sio.emit("new message", response_data, room=sid)

@sio.on("get scenario")
async def on_get_scenario(sid, data):
    """Invia lo scenario di apertura quando l'utente lo richiede dal menu."""
    user_id = user_rooms.get(sid)
    if not user_id:
        await sio.emit("error", {"message": "Not logged in"}, room=sid)
        return
    character_id = data.get("character", "")
    character = get_character(character_id)
    if not character:
        await sio.emit("error", {"message": "Character not found"}, room=sid)
        return
    from scenario_engine import get_opening_scenario
    total_msgs = count_messages(user_id, character_id)
    user_gender = user_age = sexual_orientation = None
    prefs = get_user_preferences(user_id)
    user_gender = prefs.get("user_gender") or None
    user_age = prefs.get("user_age") or None
    sexual_orientation = prefs.get("sexual_orientation") or None
    scenario_text = get_opening_scenario(character, total_msgs,
                                          user_gender=user_gender,
                                          user_age=user_age,
                                          sexual_orientation=sexual_orientation)
    if scenario_text:
        await sio.emit("scenario content", {
            "character": character_id,
            "message": scenario_text
        }, room=sid)
    else:
        await sio.emit("scenario content", {
            "character": character_id,
            "message": ""
        }, room=sid)

@sio.on("stream message")
async def on_stream_message(sid, data):
    user_id = user_rooms.get(sid)
    if not user_id:
        await sio.emit("stream error", {"message": "Not logged in"}, room=sid)
        return
    text = data.get("message", "")
    character_id = data.get("character", list_characters()[0]["id"])
    image_b64 = data.get("image", "")
    image_mime = data.get("image_mime", "image/jpeg")
    if not text and not image_b64:
        return
    if text:
        ok, msg = security_utils.nsfw_check_text(text)
        if not ok:
            await sio.emit("stream error", {"message": msg}, room=sid)
            return
    username = user_names.get(sid, "Utente")
    character = get_character(character_id)
    if not character:
        await sio.emit("stream error", {"message": "Character not found"}, room=sid)
        return
    if not _check_character_access(user_id, character):
        await sio.emit("stream error", {"message": "premium_required"}, room=sid)
        return

    await sio.emit("typing", {"username": character["name"]}, room=sid)

    stripped = text.strip()
    if stripped.startswith("/genera") or stripped.startswith("/muovi"):
        result = process_message(user_id, character_id, text, username,
                                 memory_context=data.get("memory_context"),
                                 user_memory=data.get("user_memory"),
                                 character_data=data.get("character_data"),
                                 image_base64=image_b64, image_mime=image_mime,
                                 is_favorite=data.get("is_favorite", False))
        if result:
            payload = {
                "username": character["name"],
                "message": result["ai_text"],
                "emotion": result.get("emotion", "neutro"),
                "ai_provider": result.get("ai_provider", "system"),
                "ai_model": result.get("ai_model", ""),
                "is_roleplay": True,
                "is_fallback": result.get("is_fallback", False),
            }
            if result.get("generated_image"):
                payload["generated_image"] = result["generated_image"]
            if result.get("generated_video"):
                payload["generated_video"] = result["generated_video"]
            await sio.emit("new message", payload, room=sid)
        return

    emotion, intensity, emotions = detect_emotion(text)
    relationship = get_relationship(user_id, character_id)
    personality = get_personality(character_id, character.get("core_traits", {}))
    world_state = get_world_state()
    memory_context = data.get("memory_context")
    user_memory = data.get("user_memory")
    _msg_limit = 50 if is_content_unlocked(user_id, "feature", "extended_memory") else 20
    history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=_msg_limit)
    shifts = get_recent_shifts(user_id, character_id)
    user_prefs = get_user_preferences(user_id)
    user_gender = user_prefs.get("user_gender") or None
    user_age = user_prefs.get("user_age") or None
    sexual_orientation = user_prefs.get("sexual_orientation") or None

    image_desc = None
    if image_b64:
        image_desc = image_utils.describe_image(image_b64, image_mime)
        if image_desc:
            text = (text + "\n\n[IMAGE: " + image_desc + "]") if text else "[IMAGE: " + image_desc + "]"

    is_first = count_all_user_messages(user_id) == 0
    add_message(user_id, character_id, "user", text)
    if is_first:
        credit_referral_first_message(user_id)

    evo = get_evolution(user_id, character_id)
    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)
    if evo_updates["relationship_deltas"]:
        update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
    reward = evo_updates.get("mevacoins_reward", 0)
    if reward:
        add_mevacoins(user_id, reward, f"milestone:{character_id}")
    if evo_updates["trait_modifiers"]:
        pers = get_personality(character_id, character.get("core_traits", {}))
        for trait, delta in evo_updates["trait_modifiers"].items():
            pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
        update_personality(character_id, pers)

    if not character.get("evolution"):
        rel_deltas = _compute_relationship_deltas(emotion, intensity)
        if any(v != 0 for v in rel_deltas.values()):
            update_relationship(user_id, character_id, rel_deltas)
        pers_deltas = _compute_personality_deltas(emotion, intensity, relationship)
        if any(v != 0 for v in pers_deltas.values()):
            pers = get_personality(character_id, character.get("core_traits", {}))
            for trait, delta in pers_deltas.items():
                pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
            update_personality(character_id, pers)

    learned = evo.setdefault("learned", {"topics": [], "personality_drift": {}, "new_skills": []})
    knowledge = character.get("knowledge_domains", {})
    ignorance_list = knowledge.get("ignorance", [])
    text_lower = text.lower()
    for topic in ignorance_list:
        if not isinstance(topic, str):
            continue
        keywords = [w for w in topic.lower().split() if len(w) > 3]
        if not keywords:
            keywords = [topic.lower()]
        matched = sum(1 for kw in keywords if kw in text_lower)
        if matched >= 1 and matched >= len(keywords) * 0.5:
            topic_key = f"teaching:{topic}"
            evo["flags"][topic_key] = evo["flags"].get(topic_key, 0) + 1
            if evo["flags"][topic_key] >= 3 and topic not in learned["topics"]:
                learned["topics"].append(topic)

    emotion_drift = {
        "joy": {"warmth": 0.02, "playfulness": 0.03},
        "anger": {"warmth": -0.03, "strictness": 0.02, "sarcasm": 0.03},
        "romance": {"warmth": 0.03, "playfulness": 0.02},
        "sadness": {"warmth": 0.01, "patience": 0.02},
        "challenge": {"strictness": 0.02, "sarcasm": 0.03},
    }
    drift = emotion_drift.get(emotion, {})
    for trait, delta in drift.items():
        current = learned["personality_drift"].get(trait, 0.0)
        clamped = max(-3.0, min(3.0, current + delta))
        learned["personality_drift"][trait] = round(clamped, 2)

    update_evolution(user_id, character_id, evo)

    new_name = _detect_character_rename(text)
    if new_name:
        evo["flags"]["custom_name"] = new_name
        update_evolution(user_id, character_id, evo)

    if evo.get("flags", {}).get("custom_name"):
        character = {**character, "name": evo["flags"]["custom_name"]}

    memory_updates = _extract_memory_updates(user_id, text, character, character_id)
    if memory_updates:
        wrapped = {}
        for key, val in memory_updates.items():
            wrapped[key] = {"value": val, "source": character_id, "source_name": character["name"]}
        update_user_memory(user_id, wrapped)

    stored = get_user_memory(user_id).get("memory", {})
    if stored:
        user_memory = stored

    summaries = get_memories(user_id, character_id, limit=5)
    evo["dialog_hints"] = evo_updates.get("dialog_hints", [])
    evo["_just_unlocked"] = evo_updates.get("unlocked", [])
    user_is_favorite = data.get("is_favorite", False)
    _total_msgs = count_messages(user_id, character_id)
    messages = build_messages(
        character, {"emotion": emotion, "intensity": intensity},
        relationship, personality, world_state, text, user_id, history,
        shifts, username, user_memory=user_memory, summaries=summaries,
        evolution=evo, is_favorite=user_is_favorite, total_messages=_total_msgs,
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation
    )

    await sio.emit("stream start", {
        "username": character["name"],
        "user_message": data.get("message", ""),
        "emotion": emotion,
        "intensity": intensity,
    }, room=sid)

    ai_text = ""
    ai_provider = ""
    ai_model = ""
    is_fallback = False

    try:
        for token, pid, model in ai_engine.get_ai_response_stream(messages, user_id=user_id):
            ai_text += token
            ai_provider = pid
            ai_model = model
            await sio.emit("stream token", {"token": token, "text": ai_text}, room=sid)
    except Exception as e:
        await sio.emit("stream error", {"message": str(e)}, room=sid)
        return

    if not ai_text:
        ai_text = _fallback_response(character, emotion)
        ai_provider = "fallback"
        is_fallback = True
        await sio.emit("stream token", {"token": ai_text, "text": ai_text}, room=sid)

    add_message(user_id, character_id, "assistant", ai_text)

    try:
        _maybe_summarize(user_id, character_id, character)
    except Exception:
        pass

    await sio.emit("stream complete", {
        "username": character["name"],
        "message": ai_text,
        "emotion": emotion,
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "is_roleplay": True,
        "is_fallback": is_fallback,
        "memory_updates": memory_updates or {},
        "evo_updates": {"new_stage": evo_updates.get("new_stage"), "unlocked": evo_updates.get("unlocked", [])},
    }, room=sid)

@sio.on("stream stop")
async def on_stream_stop(sid, data):
    user_id = user_rooms.get(sid)
    if user_id:
        ai_engine.STREAM_STOP_FLAGS[user_id] = True

@sio.on("typing")
async def on_typing(sid, data):
    user_id = user_rooms.get(sid)
    if not user_id:
        return
    character_id = data.get("character", list_characters()[0]["id"])
    character = get_character(character_id)
    if character:
        await sio.emit("typing", {"username": character["name"]}, room=sid)

@sio.on("stop typing")
async def on_stop_typing(sid, data):
    user_id = user_rooms.get(sid)
    if not user_id:
        return
    character_id = data.get("character", list_characters()[0]["id"])
    character = get_character(character_id)
    if character:
        await sio.emit("stop typing", {"username": character["name"]}, room=sid)

def _generate_greeting(character, character_name, username=None, user_id=None):
    from prompt_builder import build_system_prompt
    rel = get_relationship("new_user", character["id"])
    pers = get_personality(character["id"], character["core_traits"])
    ws = get_world_state()
    user_gender = user_age = sexual_orientation = None
    if user_id:
        prefs = get_user_preferences(user_id)
        user_gender = prefs.get("user_gender") or None
        user_age = prefs.get("user_age") or None
        sexual_orientation = prefs.get("sexual_orientation") or None
    sp = build_system_prompt(character, {"emotion": "neutral", "intensity": 0}, rel, pers, ws,
                             username=username, user_gender=user_gender, user_age=user_age,
                             sexual_orientation=sexual_orientation)

    # Determina livello di familiarità
    msg_count = count_messages(user_id, character["id"]) if user_id else 0
    if msg_count == 0:
        warmth = "stranger"
        warmth_desc = "Non hai mai parlato con questa persona. Fai una prima presentazione breve e naturale."
    elif msg_count <= 10:
        warmth = "acquaintance"
        warmth_desc = f"Conosci appena {username}. Saluta in modo cordiale ma non eccessivo."
    elif msg_count <= 50:
        warmth = "friend"
        warmth_desc = f"Sei abbastanza in confidenza con {username}. Saluta con calore, mostra che sei contento di rivederlo/a."
    elif msg_count <= 100:
        warmth = "close_friend"
        warmth_desc = f"Tu e {username} avete una bella amicizia. Saluta con affetto genuino, come faresti con un amico caro."
    else:
        warmth = "best_friend"
        warmth_desc = f"Tu e {username} siete molto legati. Saluta con grande affetto e intimità, come una persona cara che non vedi da tempo."

    prompt = (
        f"Livello di familiarità: {warmth}. {warmth_desc}\n"
        f"Saluta {username} in modo naturale e coerente con il tuo personaggio. "
        f"Non usare frasi fatte. Sii creativo. Massimo 1-2 frasi."
    )
    msgs = [{"role": "system", "content": sp}, {"role": "user", "content": prompt}]
    ai_text, _, _ = get_ai_response(msgs, user_id=user_id)
    if ai_text:
        return ai_text
    return _greeting_fallback(character_name, character)

def _greeting_fallback(name, character):
    cid = character["id"]
    g = {
        "ginecologa": f"*{name} ti guarda da sopra la scrivania.* Buongiorno. Sono la dottoressa Elena. Prego, si accomodi.",
        "insegnante_matematica": f"*{name} è alla lavagna e si gira.* Buongiorno. Sono il professor Marco. Prendi posto.",
        "prof_italiano": f"*{name} chiude il libro con un sorriso.* Buongiorno, giovane amico. Che piacere conoscerti.",
        "insegnante_nuoto": f"*{name} sorride raggiante.* Ciao! Benvenuto! Pronto per tuffarti?",
    }
    return g.get(cid, f"*{name} ti sorride.* Ciao! Sono {name}.")

# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    _free_port(port)
    logger.info(f"Starting on port {port}...")
    uvicorn.run("app:socket_app", host="0.0.0.0", port=port, reload=False, log_level="info")
