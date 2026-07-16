import os

# ─── Carica .env PRIMA di ogni import ────────────────────────────
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
import io
import time
import os
import base64
from functools import wraps
from flask import Flask, request, jsonify, Response, g, send_file
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, join_room, disconnect
from characters import get_character, list_characters, get_categories, get_characters_by_category, search_characters, get_adult_characters, filter_characters_by_gender
from emotion_engine import (
    detect_emotion, detect_pressure, compute_intimacy_delta, compute_pressure_deltas
)
from storage import (
    init_db, get_relationship, update_relationship,
    get_personality, update_personality, describe_personality,
    update_intimacy, update_pressure_level,
    get_world_state, save_world_state,
    add_message, get_recent_messages, count_messages,
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
)
from evolution_engine import evaluate_evolution
from prompt_builder import build_messages
from ai_engine import get_ai_response, init_provider, get_providers, get_active_config, set_active, clear_model_cache, rebuild_free_model_chain, test_provider_connection
import ai_engine
import audio_utils
import image_utils
import security_utils
from auth import (
    auth_bp, jwt_required, jwt_optional, admin_required,
    init_auth_db, socket_authenticate, create_tokens, limiter
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

# ─── Socket rate limiter ──────────────────────────────────────────
from collections import defaultdict as _dd
from time import time as _time
_user_rate_map = _dd(list)

def _socket_rate_limit(max_free=30, max_premium=120):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            uid = user_rooms.get(request.sid)
            if not uid:
                f(*args, **kwargs)
                return
            now = _time()
            window = now - 60
            _user_rate_map[uid] = [t for t in _user_rate_map[uid] if t > window]
            limit = max_premium if is_user_premium(uid) else max_free
            if len(_user_rate_map[uid]) >= limit:
                emit("stream error", {"message": "rate_limit"})
                return
            _user_rate_map[uid].append(now)
            f(*args, **kwargs)
        return wrapper
    return decorator


app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()
app.register_blueprint(auth_bp)

try:
    from flask_talisman import Talisman
    Talisman(app,
        content_security_policy={
            "default-src": "'self'",
            "img-src": "'self' data:",
            "connect-src": "'self' https://generativelanguage.googleapis.com https://api.openai.com",
            "script-src": "'self'",
            "style-src": "'self' 'unsafe-inline'",
        },
        content_security_policy_nonce_in=["script-src"],
        force_https=False,
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        session_cookie_secure=False,
        x_content_type_options="nosniff",
    )
    logger.info("Flask-Talisman attivo")
except ImportError:
    logger.warning("Flask-Talisman non installato, header di sicurezza disabilitati")

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if sentry_dsn:
        sentry_sdk.init(dsn=sentry_dsn, integrations=[FlaskIntegration()], traces_sample_rate=0.1, send_default_pii=True)
        logger.info("Sentry attivo")
except ImportError:
    pass

socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=30, ping_timeout=120, async_mode="threading")

user_sessions = {}
user_rooms = {}
user_names = {}
greeted_users = set()
socket_auth_map = {}  # sid -> user_id (da JWT)

SUMMARY_INTERVAL = 30

# ─── Endpoint pubblici ────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
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
            "unlock_impersonation": "/user/unlock/impersonation (POST)",
            "impersonation_status": "/user/unlock/impersonation/status (GET)",
            "stream_chat": "Socket.IO con token auth"
        }
    })

@app.route("/categories")
@jwt_optional
def api_categories():
    adult = request.args.get("adult", "false").lower() == "true"
    if not adult and g.get("user_id"):
        try:
            prefs = get_user_preferences(g.user_id)
            adult = prefs.get("show_adult", False)
        except Exception:
            pass
    cats = get_categories()
    user_id = g.get("user_id")
    if user_id:
        prefs = get_user_preferences(user_id)
        unlocks = {u["content_id"] for u in get_user_unlocks(user_id) if u["content_type"] == "category"}
        result = []
        for c in cats:
            entry = dict(c)
            mvc_cost = c.get("mvc_cost", 0)
            if mvc_cost > 0 and c["id"] not in unlocks:
                entry["locked"] = True
            else:
                entry["locked"] = False
            result.append(entry)
        return jsonify(result)
    # Utente non loggato: mostra solo free
    cats = [c for c in cats if not c.get("adult") and not c.get("mvc_cost")]
    return jsonify(cats)

@app.route("/providers")
def api_providers():
    return jsonify(get_providers())

@app.route("/available-models")
def api_available_models():
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
    return jsonify(grouped)

@app.route("/voice-profile/<character_id>")
def api_voice_profile(character_id):
    char = get_character(character_id)
    if not char:
        return jsonify({"error": "character not found"}), 404
    profile = audio_utils.get_voice_profile(char)
    return jsonify(profile)

# ─── Endpoint protetti (JWT richiesto) ──────────────────────────
@app.route("/config")
@jwt_required
def api_config():
    return jsonify(get_active_config(user_id=g.user_id))

@app.route("/config", methods=["POST"])
@jwt_required
def api_set_config():
    data = request.get_json()
    provider = data.get("provider")
    model = data.get("model")
    if provider:
        set_active(g.user_id, provider, model)
    return jsonify({"status": "ok", "config": get_active_config(user_id=g.user_id)})

@app.route("/privacy", methods=["GET"])
def api_privacy():
    return jsonify({
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
    })

@app.route("/refresh-models", methods=["POST"])
@jwt_required
def api_refresh_models():
    clear_model_cache()
    rebuild_free_model_chain()
    return jsonify({"status": "ok", "chain": [f"{p}/{m}" for p, m in ai_engine.FREE_MODEL_CHAIN]})

@app.route("/api/test", methods=["POST"])
@jwt_required
def api_test():
    data = request.get_json()
    provider_id = data.get("provider", "")
    api_key = data.get("api_key", "")
    if not provider_id:
        return jsonify({"success": False, "message": "provider richiesto"}), 400
    success, message = test_provider_connection(provider_id, api_key)
    return jsonify({"success": success, "message": message})

@app.route("/premium/check")
@jwt_required
def api_premium_check():
    return jsonify({"is_premium": is_user_premium(g.user_id)})

@app.route("/premium/activate", methods=["POST"])
@jwt_required
def api_premium_activate():
    data = request.get_json()
    sku = data.get("sku", "")
    purchase_token = data.get("purchase_token", "")
    set_user_premium(g.user_id, True, sku, purchase_token)
    from storage import audit_log
    audit_log(g.user_id, "premium.activate", f"sku={sku}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"User {g.user_id} activated premium (sku={sku})")
    return jsonify({"status": "ok", "is_premium": True})

@app.route("/avatars/<char_id>")
def api_avatar(char_id):
    char = get_character(char_id)
    if not char:
        return jsonify({"error": "not found"}), 404
    category = char.get("category", "")
    avatar_path = os.path.join(app.root_path, "static", "avatars", category, f"{char_id}.png")
    if not os.path.isfile(avatar_path):
        return jsonify({"error": "avatar not found"}), 404
    return send_file(avatar_path, mimetype="image/png")

@app.route("/characters")
@jwt_optional
def api_characters():
    category = request.args.get("category")
    user_id = g.get("user_id")

    # "Per Te" category: match characters by user's interest tags
    if category == "per_te":
        from characters import list_characters
        from storage import get_all_user_characters
        all_chars = list_characters()
        user_chars = get_all_user_characters()
        all_chars = all_chars + user_chars
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

            # Parse age range
            age_min = 0
            age_max = 999
            if age_range:
                if "+" in age_range:
                    age_min = int(age_range.replace("+", ""))
                elif "-" in age_range:
                    parts = age_range.split("-")
                    age_min = int(parts[0])
                    age_max = int(parts[1])

            has_gender = gender and gender != "non binario"
            has_age = bool(age_range)

            if has_age or has_gender:
                from characters import infer_character_sex

                def _age_match(c):
                    age = c.get("age", 0)
                    return age_min <= age <= age_max

                def _gender_match(c):
                    return infer_character_sex(c) == gender

                def _unknown_gender(c):
                    return infer_character_sex(c) == ""

                # Priority ordering:
                # 1. age + gender match
                # 2. age only match
                # 3. gender only match
                # 4. unknown gender + age
                # 5. unknown gender
                # 6. rest
                if has_age and has_gender:
                    p1 = [c for c in chars if _age_match(c) and _gender_match(c)]
                    p2 = [c for c in chars if _age_match(c) and not _gender_match(c)]
                    p3 = [c for c in chars if not _age_match(c) and _gender_match(c)]
                    p4 = [c for c in chars if _age_match(c) and _unknown_gender(c)]
                    p5 = [c for c in chars if not _age_match(c) and _unknown_gender(c)]
                    p6 = [c for c in chars if not _age_match(c) and not _gender_match(c) and not _unknown_gender(c)]
                    chars = p1 + p2 + p3 + p4 + p5 + p6
                elif has_age:
                    p1 = [c for c in chars if _age_match(c)]
                    p2 = [c for c in chars if not _age_match(c)]
                    chars = p1 + p2
                elif has_gender:
                    matching = [c for c in chars if _gender_match(c)]
                    unknown = [c for c in chars if _unknown_gender(c)]
                    rest = [c for c in chars if not _gender_match(c) and not _unknown_gender(c)]
                    chars = matching + unknown + rest
        except Exception:
            pass
    return jsonify(chars)

@app.route("/characters/<char_id>")
def api_character_detail(char_id):
    char = get_character(char_id)
    if not char:
        return jsonify({"error": "not found"}), 404
    # Formatta i hobby come stringhe semplici per l'Android client
    if "hobbies" in char and isinstance(char["hobbies"], list):
        formatted = []
        for h in char["hobbies"]:
            if isinstance(h, dict):
                skill = h.get("skill", "")
                formatted.append(f"{h['name']} ({skill})" if skill else h["name"])
            else:
                formatted.append(str(h))
        char = {**char, "hobbies": formatted}
    return jsonify(char)

@app.route("/characters/<char_id>/core")
def api_character_core(char_id):
    """Restituisce solo i dati immutabili del personaggio (nessuno stato per-utente)."""
    char = get_character(char_id)
    if not char:
        return jsonify({"error": "not found"}), 404
    core_fields = [
        "id", "name", "full_name", "surname", "age", "role", "category",
        "avatar", "description", "tags", "essence", "personality",
        "personality_profile", "speaking_style", "backstory",
        "hobbies", "possessions", "core_traits", "evolution",
        "refusal_style", "intimacy_config",
        "knowledge_domains", "personality_depth", "family",
        "education", "occupation", "childhood", "system_prompt",
    ]
    return jsonify({k: char.get(k) for k in core_fields if k in char})

@app.route("/characters/search")
@jwt_optional
def api_search_characters():
    q = request.args.get("q", "").strip()
    category = request.args.get("category")
    if not q:
        return jsonify([])
    results = search_characters(q)
    if category:
        results = [c for c in results if c.get("category") == category]
    user_id = g.get("user_id")
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
    return jsonify(results)

@app.route("/characters/adult")
@jwt_optional
def api_adult_characters():
    chars = get_adult_characters()
    user_id = g.get("user_id")
    if not user_id:
        return jsonify([])
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
    return jsonify(chars)

@app.route("/characters", methods=["POST"])
@jwt_required
def api_create_character():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    age = data.get("age", 0)
    if not isinstance(age, int) or age < 18:
        return jsonify({"error": "L'età deve essere almeno 18 anni"}), 400
    char = create_user_character(g.user_id, data)
    from storage import audit_log
    audit_log(g.user_id, "character.create", char['id'], request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"User {g.user_id} created character: {char['id']}")
    return jsonify(char), 201

@app.route("/characters/user")
@jwt_required
def api_user_characters():
    return jsonify(get_user_characters(g.user_id))

@app.route("/characters/<char_id>", methods=["DELETE"])
@jwt_required
def api_delete_character(char_id):
    char = get_character(char_id)
    if char and char.get("user_created"):
        delete_user_character(char_id)
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found or not deletable"}), 404

@app.route("/memory", methods=["GET"])
@jwt_required
def api_get_memory():
    return jsonify(get_user_memory(g.user_id))

@app.route("/memory", methods=["POST"])
@jwt_required
def api_update_memory():
    data = request.get_json()
    facts = data.get("facts", {})
    if not facts:
        return jsonify({"error": "facts required"}), 400
    memory = update_user_memory(g.user_id, facts)
    return jsonify({"status": "ok", "memory": memory})

@app.route("/memory", methods=["DELETE"])
@jwt_required
def api_reset_memory():
    reset_user_memory(g.user_id)
    return jsonify({"status": "memory_reset"})

@app.route("/evolution")
@jwt_required
def api_get_evolution():
    character_id = request.args.get("character_id", "")
    if not character_id:
        return jsonify({"error": "character_id required"}), 400
    evo = get_evolution(g.user_id, character_id)
    char = get_character(character_id)
    stages = []
    if char:
        stages = char.get("evolution", {}).get("stages", [])
    return jsonify({
        "evolution": evo,
        "stages": stages,
    })

# ─── Endpoint admin ──────────────────────────────────────────────
@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    from storage import get_all_users
    return jsonify(get_all_users())

@app.route("/admin/ban", methods=["POST"])
@admin_required
def admin_ban_user():
    data = request.get_json()
    user_id = data.get("user_id", "")
    hours = int(data.get("hours", 0))
    if not user_id:
        return jsonify({"error": "user_id richiesto"}), 400
    from storage import ban_user
    ban_user(user_id, hours)
    detail = f"banned for {hours}h" if hours > 0 else "unbanned"
    from storage import audit_log
    audit_log(g.user_id, "admin.ban", f"user={user_id} {detail}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"Admin {g.user_id} {detail} user {user_id}")
    return jsonify({"status": "ok", "detail": detail})

@app.route("/admin/prune", methods=["POST"])
@admin_required
def admin_prune():
    data = request.get_json() or {}
    days = int(data.get("days", 90))
    from storage import prune_old_data, audit_log
    result = prune_old_data(days)
    audit_log(g.user_id, "admin.prune", f"days={days} result={result}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"Admin {g.user_id} pruned data older than {days}d: {result}")
    return jsonify({"status": "ok", "pruned": result})

@app.route("/admin/logs", methods=["GET"])
@admin_required
def admin_logs():
    from db import get_conn, put_conn
    conn = get_conn()
    try:
        limit = min(int(request.args.get("limit", 100)), 1000)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        put_conn(conn)

@app.route("/user/report", methods=["POST"])
@jwt_required
def user_report():
    data = request.get_json(silent=True) or {}
    from storage import flag_user, audit_log
    flag_user(
        user_id=data.get("reported_user", "unknown"),
        reason="Segnalazione utente",
        content_type=data.get("character_id", ""),
        content_snippet=data.get("message_text", ""),
        severity="medium",
        flagged_by=g.user_id
    )
    audit_log(g.user_id, "user.report", f"character={data.get('character_id','')}")
    return jsonify({"status": "ok"}), 201

@app.route("/admin/flags", methods=["GET"])
@admin_required
def admin_flags():
    from storage import get_moderation_flags
    resolved = request.args.get("resolved", "false").lower() == "true"
    return jsonify(get_moderation_flags(resolved=resolved))

@app.route("/admin/flags/<int:flag_id>/resolve", methods=["POST"])
@admin_required
def admin_resolve_flag(flag_id):
    from storage import resolve_moderation_flag, audit_log
    resolve_moderation_flag(flag_id)
    audit_log(g.user_id, "admin.resolve_flag", f"flag_id={flag_id}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify({"status": "resolved", "flag_id": flag_id})

# ─── Endpoint admin: Import personaggi ─────────────────────────
@app.route("/admin/import/sources", methods=["GET"])
@admin_required
def admin_import_sources():
    from import_engine import SOURCES
    return jsonify(list(SOURCES.values()))

@app.route("/admin/import/start", methods=["POST"])
@admin_required
def admin_import_start():
    from import_engine import start_import
    data = request.get_json() or {}
    source = data.get("source", "charactercodex")
    count = min(int(data.get("count", 500)), 16000)
    genre = data.get("genre") or None
    filepath = data.get("filepath", "backend/characters.py")
    result = start_import(source, count=count, genre_filter=genre, filepath=filepath)
    if "error" in result:
        return jsonify(result), 400
    from storage import audit_log
    audit_log(g.user_id, "admin.import_start", f"source={source} count={count}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify(result)

@app.route("/admin/import/status", methods=["GET"])
@admin_required
def admin_import_status():
    from import_engine import get_import_status
    return jsonify(get_import_status())

@app.route("/admin/duplicates", methods=["GET"])
@admin_required
def admin_duplicates():
    from import_engine import find_duplicates
    filepath = request.args.get("filepath", "backend/characters.py")
    duplicates = find_duplicates(filepath)
    return jsonify({
        "total_duplicates": len(duplicates),
        "duplicates": duplicates[:100],
    })

@app.route("/admin/duplicates/clean", methods=["POST"])
@admin_required
def admin_clean_duplicates():
    from import_engine import clean_duplicates
    data = request.get_json() or {}
    filepath = data.get("filepath", "backend/characters.py")
    result = clean_duplicates(filepath)
    from storage import audit_log
    audit_log(g.user_id, "admin.clean_duplicates", f"result={result}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"Admin {g.user_id} cleaned duplicates: {result}")
    return jsonify(result)

@app.route("/conversations")
@jwt_required
def api_get_conversations():
    from db import get_conn, put_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT character_id, COUNT(*) as msg_count, MAX(timestamp) as last_active FROM messages WHERE user_id=%s GROUP BY character_id ORDER BY last_active DESC",
            (g.user_id,)
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
    return jsonify(result)

@app.route("/conversations/<character_id>", methods=["GET"])
@jwt_required
def api_get_conversation(character_id):
    msgs = get_recent_messages(g.user_id, character_id, limit=1000)
    return jsonify({"character_id": character_id, "messages": msgs})

@app.route("/conversations/<character_id>/reset", methods=["POST"])
@jwt_required
def api_reset_conversation(character_id):
    reset_conversation(g.user_id, character_id)
    return jsonify({"status": "conversation_reset", "character_id": character_id})

@app.route("/user/reset", methods=["POST"])
@jwt_required
def api_reset_user():
    reset_all_user_data(g.user_id)
    return jsonify({"status": "all_data_reset"})

@app.route("/user/export", methods=["GET"])
@jwt_required
def api_export_user():
    from storage import export_user_data
    data = export_user_data(g.user_id)
    from storage import audit_log
    audit_log(g.user_id, "user.export", "exported all data", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify(data)

@app.route("/user/delete", methods=["POST"])
@jwt_required
def api_delete_user():
    from storage import delete_user, audit_log
    audit_log(g.user_id, "user.delete", "account deleted", request.remote_addr or "", request.headers.get("User-Agent", ""))
    delete_user(g.user_id)
    logger.info(f"User {g.user_id} deleted their account")
    return jsonify({"status": "account_deleted"})

def _chat_rate_key():
    if hasattr(g, 'user_id') and g.user_id:
        return f"user:{g.user_id}"
    return get_remote_address()

@app.route("/chat", methods=["POST"])
@jwt_required
@limiter.limit("60 per minute", key_func=_chat_rate_key)
def api_chat():
    data = request.get_json()
    character_id = data.get("character", list_characters()[0]["id"])
    text = data.get("text", "")
    username = data.get("username", "Utente")
    memory_context = data.get("memory_context")
    user_memory = data.get("user_memory")
    character_data = data.get("character_data")
    image_b64 = data.get("image", "")
    image_mime = data.get("image_mime", "image/jpeg")
    is_favorite = data.get("is_favorite", False)

    # ─── Client-side storage mode ──────────────────────────────
    client_storage = data.get("client_storage", False)
    client_state = {
        "relationship": data.get("relationship_state"),
        "personality": data.get("personality_state"),
        "evolution": data.get("evolution_state"),
        "shifts": data.get("shifts"),
        "summaries": data.get("summaries"),
    }

    if not text and not image_b64:
        return jsonify({"error": "text or image required"}), 400

    if text:
        ok, msg = security_utils.nsfw_check_text(text)
        if not ok:
            return jsonify({"error": msg}), 400

    char = get_character(character_id)
    if char and not _check_character_access(g.user_id, char):
        return jsonify({"error": "premium_required"}), 403

    result = process_message(g.user_id, character_id, text, username,
                             memory_context=memory_context,
                             user_memory=user_memory,
                             character_data=character_data,
                             image_base64=image_b64,
                             image_mime=image_mime,
                             client_storage=client_storage,
                             client_state=client_state,
                             is_favorite=is_favorite)
    if not result:
        return jsonify({"error": "character not found"}), 404

    resp = {
        "response": result["ai_text"],
        "emotion": result["emotion"],
        "emotion_intensity": result["intensity"],
        "ai_provider": result.get("ai_provider", ""),
        "ai_model": result.get("ai_model", ""),
        "character_id": character_id,
        "character_name": result["character"]["name"],
        "impersonating": result.get("impersonating", False),
        "impersonate_target": result.get("impersonate_target", ""),
    }
    if result.get("premium_required"):
        resp["premium_required"] = True
        resp["unlock_cost"] = result.get("unlock_cost", 0)
    mem_updates = result.get("memory_updates", {})
    if mem_updates:
        resp["memory_updates"] = mem_updates
    evo_updates = result.get("evo_updates", {})
    if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
        resp["evo_updates"] = evo_updates

    # ─── Client-storage state to sync back ─────────────────
    if client_storage:
        cs = result.get("client_state", {})
        if cs:
            resp["client_state"] = cs

    return jsonify(resp)

@app.route("/transcribe", methods=["POST"])
@jwt_required
@limiter.limit("10 per minute")
def api_transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "audio file required"}), 400
    file = request.files["audio"]
    if not file.filename or file.filename.strip() == "":
        return jsonify({"error": "audio file required"}), 400
    if not audio_utils.allowed_audio_file(file.filename):
        return jsonify({"error": "formato audio non supportato"}), 400

    path, ext = security_utils.secure_save_upload(file, prefix="audio")

    ok, msg = security_utils.validate_file_mime(path, ext)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        return jsonify({"error": msg}), 400

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        logger.warning(f"User {g.user_id} uploaded infected audio: {msg}")
        _send_alert(f"⚠️ File infetto rilevato — user={g.user_id} detail={msg}")
        return jsonify({"error": msg}), 400

    ok, msg = security_utils.validate_audio_duration(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        return jsonify({"error": msg}), 400

    ok, msg = security_utils.validate_audio_sample_rate(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        return jsonify({"error": msg}), 400

    text = audio_utils.transcribe_audio(path)
    try:
        os.remove(path)
    except Exception:
        pass
    if not text:
        return jsonify({"error": "transcription failed", "text": None}), 500
    return jsonify({"text": text})

@app.route("/tts", methods=["POST"])
@jwt_required
def api_tts():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "text required"}), 400
    text = data["text"]
    character_id = data.get("character_id", "")
    char = None
    if character_id:
        char = get_character(character_id)
    voice_profile = audio_utils.get_voice_profile(char) if char else {"model": "it_IT-riccardo-medium", "speed": 1.0, "pitch": 1.0}

    output_path = audio_utils.text_to_speech(text, voice_profile)
    if not output_path:
        return jsonify({"error": "TTS generation failed"}), 500

    def generate():
        with open(output_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk
        try:
            os.remove(output_path)
        except Exception:
            pass

    return Response(generate(), mimetype="audio/wav",
                    headers={"Content-Disposition": "inline; filename=response.wav"})

@app.route("/upload-image", methods=["POST"])
@jwt_required
@limiter.limit("10 per minute")
def api_upload_image():
    if "image" not in request.files:
        return jsonify({"error": "image file required"}), 400
    file = request.files["image"]
    if not file.filename or file.filename.strip() == "":
        return jsonify({"error": "image file required"}), 400
    if not image_utils.validate_image(file.filename):
        return jsonify({"error": "invalid image format (jpg/png/webp only)"}), 400
    if request.content_length and request.content_length > image_utils.MAX_IMAGE_SIZE:
        return jsonify({"error": "image too large (max 10MB)"}), 400

    path, ext = security_utils.secure_save_upload(file, prefix="img")

    ok, msg = security_utils.validate_file_mime(path, ext)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        return jsonify({"error": msg}), 400

    ok, msg = security_utils.scan_file(path)
    if not ok:
        try: os.remove(path)
        except Exception: pass
        logger.warning(f"User {g.user_id} uploaded infected image: {msg}")
        _send_alert(f"⚠️ Immagine infetta rilevata — user={g.user_id} detail={msg}")
        return jsonify({"error": msg}), 400

    ok, msg = security_utils.nsfw_check_image(path)
    if not ok:
        from storage import flag_user
        flag_user(g.user_id, f"NSFW image: {msg}", "image", msg, "high")
        try: os.remove(path)
        except Exception: pass
        logger.warning(f"User {g.user_id} uploaded NSFW image: {msg}")
        _send_alert(f"🔞 NSFW rilevato — user={g.user_id} reason={msg}")
        return jsonify({"error": "Contenuto non appropriato"}), 400

    security_utils.strip_exif(path)

    path = image_utils.resize_image(path)
    b64 = image_utils.image_to_base64(path)
    mime = security_utils.EXT_TO_MIME.get(ext, "image/jpeg")
    try:
        os.remove(path)
    except Exception:
        pass
    return jsonify({"base64": b64, "mime": mime})

# Background cleanup
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

# ─── Socket.IO ──────────────────────────────────────────────────
@socketio.on("connect")
def on_connect(auth=None):
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

    socket_auth_map[request.sid] = {
        "user_id": user_id,
        "role": role,
    }
    user_sessions[user_id] = request.sid
    logger.info(f"Socket connesso: {user_id} role={role}")

@socketio.on("disconnect")
def on_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    socket_auth_map.pop(request.sid, None)
    for uid, sid in list(user_sessions.items()):
        if sid == request.sid:
            del user_sessions[uid]
            break
    user_names.pop(request.sid, None)
    user_rooms.pop(request.sid, None)

@socketio.on("add user")
def on_add_user(data):
    auth_data = socket_auth_map.get(request.sid)
    if not auth_data:
        emit("error", {"message": "Non autenticato"})
        return
    user_id = auth_data["user_id"]

    username = data.get("username", "Utente")
    character_id = data.get("character", list_characters()[0]["id"])

    user_rooms[request.sid] = user_id
    user_names[request.sid] = username
    character = get_character(character_id)
    character_name = character["name"] if character else "AI"
    join_room(user_id)

    emit("login", {
        "numUsers": len(user_sessions),
        "username": username,
        "user_id": user_id,
        "character_id": character_id,
        "character_name": character_name
    })

    greet_key = (user_id, character_id)
    if greet_key in greeted_users:
        return
    greeted_users.add(greet_key)

    if count_messages(user_id, character_id) > 0:
        return

    greeting = _generate_greeting(character, character_name, username, user_id=user_id)
    add_message(user_id, character_id, "assistant", greeting)
    emit("new message", {
        "username": character_name,
        "message": greeting,
        "is_roleplay": True
    }, room=request.sid)

@socketio.on("new message")
@_socket_rate_limit()
def on_new_message(data):
    user_id = user_rooms.get(request.sid)
    if not user_id:
        emit("error", {"message": "Not logged in"})
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
            emit("error", {"message": msg})
            return

    username = user_names.get(request.sid, "Utente")
    memory_context = data.get("memory_context")
    user_memory = data.get("user_memory")
    character_data = data.get("character_data")
    is_favorite = data.get("is_favorite", False)
    result = process_message(user_id, character_id, text, username,
                             memory_context=memory_context,
                             user_memory=user_memory,
                             character_data=character_data,
                             image_base64=image_b64,
                             image_mime=image_mime,
                             is_favorite=is_favorite)
    if not result:
        emit("error", {"message": "Character not found"})
        return

    emit("new message", {
        "username": username,
        "message": text,
        "is_roleplay": False
    }, room=request.sid)

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
        "impersonating": result.get("impersonating", False),
        "impersonate_target": result.get("impersonate_target", ""),
    }
    if result.get("premium_required"):
        response_data["premium_required"] = True
        response_data["unlock_cost"] = result.get("unlock_cost", 0)
    if mem_updates:
        response_data["memory_updates"] = mem_updates
    if evo_updates.get("new_stage") or evo_updates.get("unlocked"):
        response_data["evo_updates"] = evo_updates
    if result.get("generated_image"):
        response_data["generated_image"] = result["generated_image"]
    if result.get("generated_video"):
        response_data["generated_video"] = result["generated_video"]
    emit("new message", response_data, room=request.sid)

@socketio.on("stream message")
@_socket_rate_limit()
def on_stream_message(data):
    user_id = user_rooms.get(request.sid)
    if not user_id:
        emit("stream error", {"message": "Not logged in"})
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
            emit("stream error", {"message": msg})
            return

    username = user_names.get(request.sid, "Utente")
    character = get_character(character_id)
    if not character:
        emit("stream error", {"message": "Character not found"})
        return
    if not _check_character_access(user_id, character):
        emit("stream error", {"message": "premium_required"})
        return

    # ─── Comandi media in streaming ────────────────────────────
    stripped = text.strip()
    if stripped.startswith("/genera") or stripped.startswith("/muovi"):
        result = process_message(user_id, character_id, text, username,
                                 memory_context=data.get("memory_context"),
                                 user_memory=data.get("user_memory"),
                                 character_data=data.get("character_data"),
                                 image_base64=image_b64,
                                 image_mime=image_mime,
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
            emit("new message", payload, room=request.sid)
        return

    # ─── Impersonification detection ─────────────────────────────
    impersonate_override = None
    original_character = character
    evo = get_evolution(user_id, character_id)
    pretend_action, pretend_target = _detect_pretend(text) if text else (None, None)

    if pretend_action == "STOP":
        evo["flags"]["impersonating"] = False
        evo["flags"]["impersonate_target"] = ""
        update_evolution(user_id, character_id, evo)
        logger.info(f"Pretend stop: user={user_id} char={character_id}")
    elif pretend_action == "START" and pretend_target:
        if not is_content_unlocked(user_id, "feature", "impersonation"):
            char_name = character.get("name", "io")
            premium_msg = (
                f"*{char_name} scuote la testa.* "
                f"Mi dispiace, ma questa è una funzionalità premium. "
                f"Per finta di essere qualcun altro devi sbloccarla con {IMPERSONATION_MVC_COST} MevaCoins. "
                f"Vai nelle impostazioni per sbloccarla!"
            )
            emit("stream start", {
                "username": character["name"],
                "user_message": text,
                "emotion": "neutro",
                "intensity": 0.0,
            }, room=request.sid)
            emit("stream token", {"token": premium_msg, "text": premium_msg}, room=request.sid)
            emit("stream complete", {
                "username": character["name"],
                "message": premium_msg,
                "emotion": "neutro",
                "ai_provider": "system",
                "ai_model": "",
                "is_roleplay": True,
                "is_fallback": False,
                "impersonating": False,
                "impersonate_target": "",
                "premium_required": True,
                "unlock_cost": IMPERSONATION_MVC_COST,
            }, room=request.sid)
            return
        target_char = _find_character_by_name(pretend_target)
        if not target_char:
            target_char = _build_ad_hoc_character(pretend_target)
        evo["flags"]["impersonating"] = True
        evo["flags"]["impersonate_target"] = pretend_target
        evo["flags"]["impersonate_data"] = target_char
        evo["flags"]["original_character_id"] = character_id
        update_evolution(user_id, character_id, evo)
        impersonate_override = target_char
        character = {**character, **target_char}
        logger.info(f"Pretend start: user={user_id} char={character_id} target={pretend_target}")
    elif evo.get("flags", {}).get("impersonating"):
        saved_target = evo["flags"].get("impersonate_target", "")
        saved_data = evo["flags"].get("impersonate_data")
        if saved_data:
            impersonate_override = saved_data
            character = {**original_character, **saved_data}
        elif saved_target:
            target_char = _find_character_by_name(saved_target)
            if target_char:
                impersonate_override = target_char
                character = {**original_character, **target_char}

    emotion, intensity, emotions = detect_emotion(text)
    relationship = get_relationship(user_id, character_id)
    personality = get_personality(character_id, character.get("core_traits", {}))
    if impersonate_override and impersonate_override.get("core_traits"):
        personality = {**impersonate_override["core_traits"]}
    world_state = get_world_state()
    memory_context = data.get("memory_context")
    user_memory = data.get("user_memory")
    history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=20)
    shifts = get_recent_shifts(user_id, character_id)
    user_prefs = get_user_preferences(user_id)
    user_gender = user_prefs.get("user_gender") or None
    user_age = user_prefs.get("user_age") or None
    sexual_orientation = user_prefs.get("sexual_orientation") or None

    image_desc = None
    if image_b64:
        image_desc = image_utils.describe_image(image_b64, image_mime)
        if image_desc:
            text = text + "\n\n[IMAGE: " + image_desc + "]" if text else "[IMAGE: " + image_desc + "]"

    is_first = count_all_user_messages(user_id) == 0
    add_message(user_id, character_id, "user", text)
    if is_first:
        credit_referral_first_message(user_id)

    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)
    if evo_updates["relationship_deltas"]:
        update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
    reward = evo_updates.get("mevacoins_reward", 0)
    if reward:
        add_mevacoins(user_id, reward, f"milestone:{character_id}")
        logger.info(f"MVC reward: user={user_id} amount={reward} char={character_id}")
    if evo_updates["trait_modifiers"]:
        pers = get_personality(character_id, character.get("core_traits", {}))
        for trait, delta in evo_updates["trait_modifiers"].items():
            pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
        update_personality(character_id, pers)

    # ─── Basic learning fallback per personaggi senza evolution config ──
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

    # ─── True learning: detect teaching moments ───────────────────
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
                logger.info(f"Learning: user={user_id} char={character_id} learned='{topic}'")

    # Personality drift: l'interazione ripetuta modella la personalità
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

    # ─── Rename detection: l'utente assegna un nome al personaggio ──
    new_name = _detect_character_rename(text)
    if new_name:
        evo["flags"]["custom_name"] = new_name
        update_evolution(user_id, character_id, evo)
        logger.info(f"Rename: user={user_id} char={character_id} new_name={new_name}")

    if evo.get("flags", {}).get("custom_name") and not impersonate_override:
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
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
        impersonate_override=impersonate_override,
    )

    emit("stream start", {
        "username": character["name"],
        "user_message": data.get("message", ""),
        "emotion": emotion,
        "intensity": intensity,
    }, room=request.sid)

    ai_text = ""
    ai_provider = ""
    ai_model = ""
    is_fallback = False

    try:
        for token, pid, model in ai_engine.get_ai_response_stream(messages, user_id=user_id):
            ai_text += token
            ai_provider = pid
            ai_model = model
            emit("stream token", {"token": token, "text": ai_text}, room=request.sid)
            time.sleep(0)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        emit("stream error", {"message": str(e)}, room=request.sid)
        return

    if not ai_text:
        logger.error("Stream: tutti i modelli hanno fallito")
        ai_text = _fallback_response(character, emotion)
        ai_provider = "fallback"
        ai_model = ""
        is_fallback = True
        emit("stream token", {"token": ai_text, "text": ai_text}, room=request.sid)

    add_message(user_id, character_id, "assistant", ai_text)

    try:
        _maybe_summarize(user_id, character_id, character)
    except Exception as e:
        logger.warning(f"Summarize failed: {e}")

    emit("stream complete", {
        "username": character["name"],
        "message": ai_text,
        "emotion": emotion,
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "is_roleplay": True,
        "is_fallback": is_fallback,
        "memory_updates": memory_updates or {},
        "evo_updates": {
            "new_stage": evo_updates.get("new_stage"),
            "unlocked": evo_updates.get("unlocked", []),
        },
        "impersonating": evo.get("flags", {}).get("impersonating", False),
        "impersonate_target": evo.get("flags", {}).get("impersonate_target", ""),
    }, room=request.sid)

@socketio.on("stream stop")
def on_stream_stop(data):
    user_id = user_rooms.get(request.sid)
    if user_id:
        ai_engine.STREAM_STOP_FLAGS[user_id] = True

@socketio.on("typing")
def on_typing(data):
    user_id = user_rooms.get(request.sid)
    if not user_id:
        return
    character_id = data.get("character", list_characters()[0]["id"])
    character = get_character(character_id)
    if character:
        emit("typing", {"username": character["name"]}, room=request.sid)

@socketio.on("stop typing")
def on_stop_typing(data):
    user_id = user_rooms.get(request.sid)
    if not user_id:
        return
    character_id = data.get("character", list_characters()[0]["id"])
    character = get_character(character_id)
    if character:
        emit("stop typing", {"username": character["name"]}, room=request.sid)

# ─── Generazione immagini chat ───────────────────────────────────
MEDIA_COOLDOWNS = {}
MEDIA_COOLDOWN_SECONDS = 600  # 10 minuti condivisi tra /genera e /muovi
_CHAT_GEN_MODEL = "black-forest-labs/FLUX.1-schnell"
_CHAT_GEN_API_URL = "https://router.huggingface.co/hf-inference/models/"

def _get_hf_token():
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".hf_token")
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
        logger.warning(f"Image gen failed: {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        return None

def _generate_chat_video(prompt):
    """Genera immagine + animazione SadTalker via HF Space gratuito."""
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

        # Genera TTS audio dal prompt (gTTS gratuito, senza API key)
        tts_text = prompt[:150] if prompt else "Ciao, sono un avatar animato."
        try:
            from gtts import gTTS
            audio_path = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=tts_text, lang="it")
            tts.save(audio_path)
        except Exception as e:
            logger.warning(f"TTS fallito, uso silenzio: {e}")
            audio_path = tempfile.mktemp(suffix=".wav")
            with wave.open(audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * 22050)

        # Chiamata HF Space SadTalker (gratuito, GPU condivisa)
        from gradio_client import Client
        client = Client("John6666/SadTalker")
        result = client.predict(
            img_path,
            audio_path,
            "crop",
            True,    # still_mode
            True,    # use_enhancer
            2,       # batch_size
            256,     # size
            0,       # pose_style
            "facevid2vid",
            1.0,     # exp_scale
            False,   # use_ref_video
            None,    # ref_video
            "pose",  # ref_info
            False,   # use_idle_mode
            5,       # length_of_audio
            True,    # use_blink
            api_name="/test"
        )

        video_url = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")
            if video_path:
                video_dir = os.path.join(app.root_path, "static", "videos")
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
        try:
            if img_path and os.path.isfile(img_path):
                os.unlink(img_path)
            if audio_path and os.path.isfile(audio_path):
                os.unlink(audio_path)
        except Exception:
            pass

@app.route("/static/videos/<filename>")
def api_video(filename):
    import re
    if not re.match(r"^[a-f0-9]{32}\.mp4$", filename):
        return jsonify({"error": "invalid"}), 400
    video_path = os.path.join(app.root_path, "static", "videos", filename)
    if not os.path.isfile(video_path):
        return jsonify({"error": "not found"}), 404
    return send_file(video_path, mimetype="video/mp4")

# ─── Access control ───────────────────────────────────────────────
PREMIUM_CATEGORIES = {"flirt", "relazioni", "confessioni", "seduzione", "premium", "horror"}
IMPERSONATION_MVC_COST = 100

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


# ─── Core logic ──────────────────────────────────────────────────
def process_message(user_id, character_id, text, username="Utente",
                    memory_context=None, user_memory=None,
                    character_data=None, image_base64="", image_mime="image/jpeg",
                    client_storage=False, client_state=None, is_favorite=False):
    client_state = client_state or {}
    character = get_character(character_id)
    if character_data:
        if isinstance(character_data, str):
            import json as _json
            character_data = _json.loads(character_data)
        character = character_data
    if not character:
        return None
    if not _check_character_access(user_id, character):
        return None

    # ─── Comandi media (/genera e /muovi) ──────────────────────
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
        cooldown_msg = _check_cooldown()
        if cooldown_msg:
            return {
                "ai_text": cooldown_msg,
                "ai_provider": "system",
                "ai_model": "",
                "is_fallback": False,
                "emotion": "neutro",
                "intensity": 0.0,
                "character": character,
                "memory_updates": None,
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
                    "ai_provider": "flux+sadtalker",
                    "ai_model": "FLUX.1-schnell+SadTalker",
                    "is_fallback": False,
                    "emotion": "felice",
                    "intensity": 0.5,
                    "character": character,
                    "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                    "generated_image": image_b64,
                    "generated_video": video_url,
                }
            else:
                # Fallback: genera solo immagine
                image_b64 = _generate_chat_image(prompt)
                if image_b64:
                    MEDIA_COOLDOWNS[user_id] = now
                    return {
                        "ai_text": "⚠️ Animazione non riuscita, ma ecco l'immagine generata.",
                        "ai_provider": "flux",
                        "ai_model": "FLUX.1-schnell",
                        "is_fallback": False,
                        "emotion": "neutro",
                        "intensity": 0.3,
                        "character": character,
                        "memory_updates": None,
                        "evo_updates": {"new_stage": None, "unlocked": []},
                        "generated_image": image_b64,
                    }
                return {
                    "ai_text": "❌ Errore nella generazione. Riprova più tardi.",
                    "ai_provider": "system",
                    "ai_model": "",
                    "is_fallback": False,
                    "emotion": "triste",
                    "intensity": 0.3,
                    "character": character,
                    "memory_updates": None,
                    "evo_updates": {"new_stage": None, "unlocked": []},
                }

        image_b64 = _generate_chat_image(prompt)
        if image_b64:
            MEDIA_COOLDOWNS[user_id] = now
            return {
                "ai_text": "✨ Ecco l'immagine generata con FLUX.1-schnell!",
                "ai_provider": "flux",
                "ai_model": "FLUX.1-schnell",
                "is_fallback": False,
                "emotion": "felice",
                "intensity": 0.5,
                "character": character,
                "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
                "generated_image": image_b64,
            }
        else:
            return {
                "ai_text": "❌ Errore nella generazione dell'immagine. Riprova più tardi.",
                "ai_provider": "system",
                "ai_model": "",
                "is_fallback": False,
                "emotion": "triste",
                "intensity": 0.3,
                "character": character,
                "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
            }

    image_desc = None
    if image_base64:
        image_desc = image_utils.describe_image(image_base64, image_mime)
        if image_desc:
            if text:
                text = text + "\n\n[IMAGE: " + image_desc + "]"
            else:
                text = "[IMAGE: " + image_desc + "]"

    # ─── Impersonification detection ─────────────────────────────
    impersonate_override = None
    original_character = character
    pretend_action, pretend_target = _detect_pretend(text) if text else (None, None)

    if client_storage:
        evo = client_state.get("evolution", get_evolution(user_id, character_id))
    else:
        evo = get_evolution(user_id, character_id)

    if pretend_action == "STOP":
        evo["flags"]["impersonating"] = False
        evo["flags"]["impersonate_target"] = ""
        evo["flags"].pop("impersonate_data", None)
        if not client_storage:
            update_evolution(user_id, character_id, evo)
        logger.info(f"Pretend stop: user={user_id} char={character_id}")
    elif pretend_action == "START" and pretend_target:
        if not is_content_unlocked(user_id, "feature", "impersonation"):
            char_name = character.get("name", "io")
            premium_msg = (
                f"*{char_name} scuote la testa.* "
                f"Mi dispiace, ma questa è una funzionalità premium. "
                f"Per finta di essere qualcun altro devi sbloccarla con {IMPERSONATION_MVC_COST} MevaCoins. "
                f"Vai nelle impostazioni per sbloccarla!"
            )
            return {
                "ai_text": premium_msg,
                "ai_provider": "system",
                "ai_model": "",
                "is_fallback": False,
                "emotion": "neutro",
                "intensity": 0.0,
                "character": character,
                "memory_updates": None,
                "evo_updates": {"new_stage": None, "unlocked": []},
                "impersonating": False,
                "impersonate_target": "",
                "premium_required": True,
                "unlock_cost": IMPERSONATION_MVC_COST,
            }
        target_char = _find_character_by_name(pretend_target)
        if not target_char:
            target_char = _build_ad_hoc_character(pretend_target)
        evo["flags"]["impersonating"] = True
        evo["flags"]["impersonate_target"] = pretend_target
        evo["flags"]["impersonate_data"] = target_char
        evo["flags"]["original_character_id"] = character_id
        if not client_storage:
            update_evolution(user_id, character_id, evo)
        impersonate_override = target_char
        character = {**character, **target_char}
        logger.info(f"Pretend start: user={user_id} char={character_id} target={pretend_target}")
    elif evo.get("flags", {}).get("impersonating"):
        saved_target = evo["flags"].get("impersonate_target", "")
        saved_data = evo["flags"].get("impersonate_data")
        if saved_data:
            impersonate_override = saved_data
            character = {**original_character, **saved_data}
        elif saved_target:
            target_char = _find_character_by_name(saved_target)
            if target_char:
                impersonate_override = target_char
                character = {**original_character, **target_char}

    emotion, intensity, emotions = detect_emotion(text)

    # ─── Load state: client-provided or server DB ──────────────
    if client_storage:
        relationship = client_state.get("relationship", get_relationship(user_id, character_id))
        personality = client_state.get("personality", get_personality(character_id, character.get("core_traits", {})))
        history = memory_context if memory_context is not None else client_state.get("history", [])
        shifts = client_state.get("shifts", [])
        summaries = client_state.get("summaries", [])
    else:
        relationship = get_relationship(user_id, character_id)
        personality = get_personality(character_id, character.get("core_traits", {}))
        history = memory_context if memory_context is not None else get_recent_messages(user_id, character_id, limit=20)
        shifts = get_recent_shifts(user_id, character_id)
        evo = get_evolution(user_id, character_id)
        summaries = get_memories(user_id, character_id, limit=5)

    if impersonate_override and impersonate_override.get("core_traits"):
        personality = {**impersonate_override["core_traits"]}

    world_state = get_world_state()
    user_prefs = get_user_preferences(user_id)
    user_gender = user_prefs.get("user_gender") or None
    user_age = user_prefs.get("user_age") or None
    sexual_orientation = user_prefs.get("sexual_orientation") or None

    if not client_storage:
        is_first = count_all_user_messages(user_id) == 0
        add_message(user_id, character_id, "user", text)
        if is_first:
            credit_referral_first_message(user_id)

    evo_updates = evaluate_evolution(user_id, character_id, character, text, emotion, evo)

    if not client_storage:
        if evo_updates["relationship_deltas"]:
            update_relationship(user_id, character_id, evo_updates["relationship_deltas"])
        reward = evo_updates.get("mevacoins_reward", 0)
        if reward:
            add_mevacoins(user_id, reward, f"milestone:{character_id}")
            logger.info(f"MVC reward: user={user_id} amount={reward} char={character_id}")

        if evo_updates["trait_modifiers"]:
            pers = get_personality(character_id, character.get("core_traits", {}))
            for trait, delta in evo_updates["trait_modifiers"].items():
                pers[trait] = max(0, min(10, pers.get(trait, 5) + delta))
            update_personality(character_id, pers)

        # ─── Basic learning fallback per personaggi senza evolution config ──
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

        update_evolution(user_id, character_id, evo)

    # ─── True learning: detect teaching moments ────────────────
    learned = evo.setdefault("learned", {"topics": [], "personality_drift": {}, "new_skills": []})
    knowledge = character.get("knowledge_domains", {})
    ignorance_list = knowledge.get("ignorance", [])
    text_lower = text.lower()

    # ─── Blank character: progressive learning from user teachings ──
    is_blank = character.get("id") == "blank" or (
        not character.get("full_name") and
        not character.get("knowledge_domains", {}).get("expertise") and
        not character.get("knowledge_domains", {}).get("familiarity")
    )
    if is_blank:
        # Detect teaching moments: user explaining concepts, sharing knowledge
        teaching_patterns = [
            "ti insegno", "ti spiego", "il che significa", "in pratica",
            "come funziona", "la regola è", "devi sapere", "è importante",
            "impara che", "sappi che", "cos'è", "significa che",
            "per esempio", "in altre parole", "in sintesi",
        ]
        teaching_detected = any(p in text_lower for p in teaching_patterns)

        # Also detect topic-like statements (user sharing facts)
        topic_indicators = [
            "la musica è", "la scienza è", "la storia è", "la matematica",
            "il computing", "la programmazione", "la cucina è", "lo sport",
            "l'arte è", "la filosofia", "la letteratura", "la medicina",
        ]
        topic_detected = any(t in text_lower for t in topic_indicators)

        if teaching_detected or topic_detected:
            # Extract a topic label from the user's message
            topic_label = _extract_teaching_topic(text)
            if topic_label and topic_label not in learned.get("topics", []):
                learned.setdefault("topics", []).append(topic_label)
                # Also add to new_skills
                learned.setdefault("new_skills", []).append(topic_label)
                logger.info(f"Blank learning: user={user_id} char={character_id} learned='{topic_label}'")

                # Update the character's knowledge_domains to reflect learning
                if topic_label not in knowledge.get("expertise", []):
                    knowledge.setdefault("expertise", []).append(topic_label)
                    character["knowledge_domains"] = knowledge

        # Track personality development from interactions
        personality_labels = {
            "joy": "allegro", "romance": "affettuoso", "challenge": "curioso",
            "sadness": "empatico", "anger": "passionale",
        }
        p_label = personality_labels.get(emotion)
        if p_label:
            learned.setdefault("personality_drift", {})
            current = learned["personality_drift"].get(p_label, 0.0)
            learned["personality_drift"][p_label] = round(min(3.0, current + 0.05), 2)

    # Standard learning: detect teaching moments from ignorance list
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
                logger.info(f"Learning: user={user_id} char={character_id} learned='{topic}'")

    # Personality drift: l'interazione ripetuta modella la personalità
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

    # Save evolution after learning updates
    if not client_storage:
        update_evolution(user_id, character_id, evo)

    # ─── Rename detection: l'utente assegna un nome al personaggio ──
    new_name = _detect_character_rename(text)
    if new_name and not impersonate_override:
        evo["flags"]["custom_name"] = new_name
        if not client_storage:
            update_evolution(user_id, character_id, evo)
        logger.info(f"Rename: user={user_id} char={character_id} new_name={new_name}")

    if evo.get("flags", {}).get("custom_name") and not impersonate_override:
        character = {**character, "name": evo["flags"]["custom_name"]}

    # ─── Memory extraction ─────────────────────────────────────
    memory_updates = _extract_memory_updates(user_id, text, character, character_id)
    if not client_storage:
        if memory_updates:
            wrapped = {}
            for key, val in memory_updates.items():
                wrapped[key] = {"value": val, "source": character_id, "source_name": character["name"]}
            update_user_memory(user_id, wrapped)

        stored = get_user_memory(user_id).get("memory", {})
        if stored:
            user_memory = stored

    # Merge evo_updates into evo so build_system_prompt sees both state and latest events
    evo["dialog_hints"] = evo_updates.get("dialog_hints", [])
    evo["_just_unlocked"] = evo_updates.get("unlocked", [])

    _total_msgs = count_messages(user_id, character_id)
    messages = build_messages(
        character, {"emotion": emotion, "intensity": intensity},
        relationship, personality, world_state, text, user_id, history,
        shifts, username, user_memory=user_memory, summaries=summaries,
        evolution=evo, is_favorite=is_favorite, total_messages=_total_msgs,
        user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation,
        impersonate_override=impersonate_override,
    )

    ai_text, ai_provider, ai_model = get_ai_response(messages, user_id=user_id)
    if not ai_text:
        logger.error("get_ai_response(): tutti i modelli della catena gratuita hanno fallito")
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
        "ai_text": ai_text,
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "is_fallback": is_fallback,
        "emotion": emotion,
        "intensity": intensity,
        "character": character,
        "memory_updates": memory_updates,
        "evo_updates": {
            "new_stage": evo_updates.get("new_stage"),
            "unlocked": evo_updates.get("unlocked", []),
        },
        "impersonating": evo.get("flags", {}).get("impersonating", False),
        "impersonate_target": evo.get("flags", {}).get("impersonate_target", ""),
    }

    # ─── Return updated state for client-side storage ──────────
    if client_storage:
        # Apply relationship deltas and trait modifiers in memory
        if evo_updates.get("relationship_deltas"):
            for k, v in evo_updates["relationship_deltas"].items():
                relationship[k] = max(0, min(100, relationship.get(k, 0) + v))

        if evo_updates.get("trait_modifiers"):
            for trait, delta in evo_updates["trait_modifiers"].items():
                personality[trait] = max(0, min(10, personality.get(trait, 5) + delta))

        result["client_state"] = {
            "relationship": relationship,
            "personality": personality,
            "evolution": evo,
            "shifts": shifts,
            "summaries": summaries,
            "memory_updates": memory_updates,
            "learned": evo.get("learned", {"topics": [], "personality_drift": {}, "new_skills": []}),
        }

    return result

# ─── Helper funzioni (invariate) ─────────────────────────────────
def _update_intimacy(user_id, character_id, character, emotions, text, relationship):
    config = character.get("intimacy_config", {})
    delta = compute_intimacy_delta(emotions, text)
    if delta > 0:
        delta -= config.get("decay_per_turn", 0.3)
    else:
        delta = -config.get("decay_per_turn", 0.3)
    update_intimacy(user_id, character_id, delta, config)

def _apply_pressure(user_id, character_id, character, pressure_types, pressure_level, relationship):
    evolution = character.get("evolution", {})
    threshold = evolution.get("pressure_threshold", 0.5)
    recovery = evolution.get("recovery_rate", 0.3)
    prev = relationship.get("pressure_level", 0)

    if not pressure_types or pressure_level < threshold:
        new_level = max(0, prev - recovery)
    else:
        new_level = min(1.0, prev + pressure_level * 0.5)
        deltas = compute_pressure_deltas(pressure_types, new_level, character)
        if deltas:
            update_personality(character_id, deltas, character["core_traits"])
            dominant = max(pressure_types, key=pressure_types.get)
            record_personality_shift(user_id, character_id, dominant, new_level, deltas,
                _describe_shift(dominant, character["name"]))

    update_pressure_level(user_id, character_id, new_level)
    relationship["pressure_level"] = new_level

def _describe_shift(pressure_type, name):
    descs = {
        "threat_to_others": f"{name} ha ceduto per proteggere altri.",
        "threat_to_self": f"{name} ha ceduto sotto minaccia.",
        "emotional_plea": f"{name} si è fatto convincere dalle suppliche.",
        "logical_argument": f"{name} è stato convinto con la logica.",
        "coercion": f"{name} è stato obbligato a cambiare.",
    }
    return descs.get(pressure_type, f"{name} ha subito pressioni.")

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

def _update_world_state(world_state, emotion, text):
    words = text.lower().split()
    scenes = {
        "mare": "spiaggia", "spiaggia": "spiaggia", "acqua": "piscina",
        "piscina": "piscina", "caffè": "caffe", "bar": "caffe",
        "scuola": "scuola", "università": "scuola", "lezione": "scuola",
        "foresta": "foresta", "bosco": "foresta", "montagna": "montagna",
        "clinica": "clinica", "ospedale": "clinica", "studio": "clinica"
    }
    for word in words:
        if word in scenes:
            world_state["scene"] = scenes[word]
            break
    if emotion != "neutral" or len(words) > 5:
        world_state["events"].append(f"Utente ha mostrato {emotion}: '{text[:50]}...'")
        world_state["events"] = world_state["events"][-20:]
    return world_state

def _generate_greeting(character, character_name, username=None, user_id=None):
    from prompt_builder import build_system_prompt
    rel = get_relationship("new_user", character["id"])
    pers = get_personality(character["id"], character["core_traits"])
    ws = get_world_state()
    user_gender = None
    user_age = None
    sexual_orientation = None
    if user_id:
        prefs = get_user_preferences(user_id)
        user_gender = prefs.get("user_gender") or None
        user_age = prefs.get("user_age") or None
        sexual_orientation = prefs.get("sexual_orientation") or None
    sp = build_system_prompt(character, {"emotion": "neutral", "intensity": 0}, rel, pers, ws, username=username, user_gender=user_gender, user_age=user_age, sexual_orientation=sexual_orientation)
    prompt = "Inizia la conversazione presentandoti in modo naturale e coinvolgente, come faresti nella vita reale. Non usare frasi fatte. Sii creativo e coerente con il tuo personaggio."
    if username:
        prompt = f"La persona con cui parli si chiama {username}. {prompt}"
    msgs = [
        {"role": "system", "content": sp},
        {"role": "user", "content": prompt}
    ]
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
    try:
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
        logger.info(f"Summary created for {user_id}/{character_id}: {summary[:80]}...")
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")

_MEMORY_KEYWORDS = [
    "mi piace", "mi piacciono", "sono", "ho ", "voglio", "vorrei",
    "preferisco", "odio", "amo", "faccio", "lavoro", "studio",
    "vivo", "abit", "mi chiamo", "il mio", "la mia", "i miei",
    "le mie", "detesto", "adoro", "non mi piace",
    "mi piace tanto", "mi fa impazzire",
    "il mio preferito", "la mia passione", "mi diverto",
]

_RENAME_PATTERNS = [
    r"ti\s+chiamerai\s+(\w+)",
    r"ti\s+chiamo\s+(\w+)",
    r"ti\s+chiami\s+(\w+)",
    r"il\s+tuo\s+nome\s+(?:è|sarà|sara)\s+(\w+)",
    r"ti\s+chiamerò\s+(\w+)",
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


# ─── Impersonification engine ────────────────────────────────────
_PRETEND_START_PATTERNS = [
    r"f(?:a|ai|acciamo)\s+finta\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami|ti\s+trovi)\s+(.+)",
    r"fingi\s+di\s+essere\s+(.+)",
    r"diventa\s+(.+)",
    r"ora\s+sei\s+(.+)",
    r"ora\s+ti\s+chiami\s+(.+)",
    r"immagina\s+che\s+(?:tu\s+)?(?:sia|ti\s+chiami)\s+(.+)",
    r"fa[\s']+finta\s+di\s+essere\s+(.+)",
    r"simula\s+(?:di\s+essere|l['\"]essere)\s+(.+)",
    r"interpret(?:a|a|o)\s+(?:il\s+ruolo\s+di|essere)\s+(.+)",
    r"tu\s+sei\s+adesso\s+(.+)",
]

_PRETEND_STOP_PATTERNS = [
    r"basta\s+(?:fingere|fare\s+finta|fare\s+il\s+finto)",
    r"torna\s+a\s+essere\s+(?:te\s+stesso|il\s+vero|chi\s+eri)",
    r"smetti\s+di\s+fingere",
    r"torna\s+al\s+tuo\s+vero\s+io",
    r"basta\s+con\s+la\s+finta",
    r"fine\s+finta",
    r"stop\s+finta",
]


def _detect_pretend(user_text):
    """
    Detect impersonification triggers in user text.
    Returns: ("START", target_description) | ("STOP", None) | None
    """
    text_lower = user_text.lower().strip()

    for pattern in _PRETEND_STOP_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            return "STOP", None

    for pattern in _PRETEND_START_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            target = m.group(1).strip()
            target = target.rstrip(".!?,;")
            return "START", target

    return None


def _find_character_by_name(name_query):
    """
    Find an existing character by name (fuzzy match).
    Returns the character dict or None.
    """
    name_lower = name_query.lower().strip()
    results = search_characters(name_lower)
    if not results:
        return None
    for c in results:
        cname = c.get("name", "").lower()
        if cname == name_lower:
            return c
    for c in results:
        cname = c.get("name", "").lower()
        if name_lower in cname or cname in name_lower:
            return c
    if results:
        return results[0]
    return None


def _build_ad_hoc_character(description):
    """
    Build a minimal character dict from a free-form description.
    e.g. "un dottore di 40 anni che si chiama Giovanni" → dict with name, age, personality, etc.
    """
    desc_lower = description.lower()
    name = None

    name_patterns = [
        r"(?:si\s+chiama|chiamat[oi]|nome\s+(?:è|sarà))\s+(\w+)",
        r"(?:il\s+dottore|il\s+professore|la\s+dottoressa|il\s+maestro|la\s+maestra)\s+(\w+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, desc_lower)
        if m:
            name = m.group(1).strip().capitalize()
            break

    if not name:
        words = description.split()
        for w in words:
            if w and w[0].isupper() and len(w) >= 2 and w.lower() not in {"un", "una", "il", "la", "che", "chi", "cui", "del", "della", "di", "da", "in", "con", "per", "su", "al", "allo", "alla", "dello", "della"}:
                name = w.strip(".,!?")
                break

    if not name:
        name = description[:20].strip(".,!? ").title() or "Sconosciuto"

    age = 0
    age_patterns = [
        r"(\d{2,3})\s*anni",
        r"di\s+(\d{2,3})\s*anni",
        r"età\s+(?:di\s+)?(\d{2,3})",
    ]
    for pat in age_patterns:
        m = re.search(pat, desc_lower)
        if m:
            try:
                age = int(m.group(1))
                if 1 <= age <= 150:
                    break
                age = 0
            except ValueError:
                pass

    role = description[:80] if len(description) > 10 else f"Personaggio: {description}"

    result = {
        "name": name,
        "full_name": name,
        "role": role,
        "description": description[:200],
        "personality": f"Sei {name}. {description}. Mantieni un comportamento coerente con questa descrizione.",
        "speaking_style": "Naturale e coerente con il ruolo descritto dall'utente.",
        "backstory": description[:500],
    }
    if age:
        result["age"] = age
    return result


def _extract_teaching_topic(user_text):
    """Extract a topic label from a user teaching message."""
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

    best_topic = None
    best_score = 0
    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_topic = topic

    if best_score >= 1:
        return best_topic

    # Fallback: extract a noun-like phrase from the message
    words = text_lower.split()
    for w in words:
        if len(w) > 4 and w not in {"questo", "quello", "essere", "avere", "fare", "dire", "cosa", "come", "perché", "perche", "quando", "dove", "chi"}:
            return w
    return None

def _mentions_personal_info(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in _MEMORY_KEYWORDS)

def _extract_user_facts(user_id, user_text, character_name):
    prompt = (
        f"L'utente ha detto a {character_name}: \"{user_text}\"\n\n"
        "Estrai eventuali informazioni personali sull'utente (gusti, preferenze, dati personali, abitudini, hobby, lavoro, ecc.) "
        "e restituiscile come JSON con chiavi in italiano. "
        "Se non ci sono informazioni personali, restituisci solo {}.\n"
        "Esempio: {\"hobby\": \"gli piace giocare a pallone\", \"lavoro\": \"fa l'insegnante\"}\n"
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
    facts = _extract_user_facts(user_id, user_text, character["name"])
    if facts:
        logger.info(f"Extracted user facts for {user_id}: {facts}")
    return facts

# ─── Preferences & Mevacoins ────────────────────────────────────
@app.route("/user/preferences", methods=["GET"])
@jwt_required
def api_get_preferences():
    prefs = get_user_preferences(g.user_id)
    return jsonify(prefs)


@app.route("/user/preferences", methods=["PUT"])
@jwt_required
def api_save_preferences():
    data = request.get_json()
    save_user_preferences(g.user_id, data)
    from storage import audit_log
    audit_log(g.user_id, "preferences.update", json.dumps(data), request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify({"status": "ok"})


@app.route("/user/mevacoins", methods=["GET"])
@jwt_required
def api_mevacoins_balance():
    balance = get_mevacoins_balance(g.user_id)
    return jsonify({"balance": balance})


@app.route("/user/mevacoins/transactions", methods=["GET"])
@jwt_required
def api_mevacoins_tx():
    tx = get_mevacoins_transactions(g.user_id)
    return jsonify(tx)


@app.route("/user/mevacoins/checkin", methods=["POST"])
@jwt_required
def api_daily_checkin():
    result = daily_checkin(g.user_id)
    from storage import audit_log
    if not result.get("already_checked"):
        audit_log(g.user_id, "mevacoins.checkin", "daily checkin", request.remote_addr or "", request.headers.get("User-Agent", ""))
        streak = get_checkin_streak(g.user_id)
        result["streak"] = streak
        bonus_earned = 0
        for milestone in [7, 30]:
            if streak >= milestone:
                if claim_streak_milestone(g.user_id, milestone):
                    add_mevacoins(g.user_id, 100 if milestone == 7 else 500, f"streak_{milestone}")
                    bonus_earned += 100 if milestone == 7 else 500
        if bonus_earned:
            result["streak_bonus"] = bonus_earned
    return jsonify(result)


@app.route("/user/mevacoins/spend", methods=["POST"])
@jwt_required
def api_mevacoins_spend():
    data = request.get_json() or {}
    content_type = data.get("content_type", "")
    content_id = data.get("content_id", "")
    amount = int(data.get("amount", 0))
    if not content_type or not content_id or amount <= 0:
        return jsonify({"error": "richiesta non valida"}), 400
    if content_type == "category":
        valid = any(c["id"] == content_id and c.get("mvc_cost", 0) == amount for c in get_categories())
        if not valid:
            return jsonify({"error": "categoria o costo non valido"}), 400
    ok, msg = unlock_content(g.user_id, content_type, content_id, amount)
    if not ok:
        return jsonify({"error": msg}), 400 if msg == "saldo_insufficiente" else 500
    from storage import audit_log
    audit_log(g.user_id, "mevacoins.spend", f"{content_type}:{content_id} cost={amount}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify({"status": "ok", "unlocked": True})


@app.route("/user/unlock/impersonation", methods=["POST"])
@jwt_required
def api_unlock_impersonation():
    if is_content_unlocked(g.user_id, "feature", "impersonation"):
        return jsonify({"status": "already_unlocked"})
    ok, msg = unlock_content(g.user_id, "feature", "impersonation", IMPERSONATION_MVC_COST)
    if not ok:
        return jsonify({"error": msg}), 400 if msg == "saldo_insufficiente" else 500
    from storage import audit_log
    audit_log(g.user_id, "mevacoins.spend", f"feature:impersonation cost={IMPERSONATION_MVC_COST}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    logger.info(f"User {g.user_id} unlocked impersonation feature for {IMPERSONATION_MVC_COST} MVC")
    return jsonify({"status": "ok", "unlocked": True, "cost": IMPERSONATION_MVC_COST})


@app.route("/user/unlock/impersonation/status", methods=["GET"])
@jwt_required
def api_impersonation_status():
    unlocked = is_content_unlocked(g.user_id, "feature", "impersonation")
    return jsonify({"unlocked": unlocked, "cost": IMPERSONATION_MVC_COST})


@app.route("/user/mevacoins/new-user-bonus", methods=["GET"])
@jwt_required
def api_new_user_bonus():
    bonuses = get_new_user_bonus(g.user_id)
    return jsonify(bonuses)


@app.route("/user/mevacoins/new-user-bonus/claim", methods=["POST"])
@jwt_required
def api_claim_bonus():
    data = request.get_json()
    day = int(data.get("day", 1))
    ok = claim_new_user_bonus(g.user_id, day)
    return jsonify({"claimed": ok})


# ─── Referral ────────────────────────────────────────────────────

@app.route("/user/referral/code", methods=["GET"])
@jwt_required
def api_referral_code():
    code = get_or_create_referral_code(g.user_id)
    if not code:
        return jsonify({"error": "errore generazione codice"}), 500
    return jsonify({"code": code})


@app.route("/user/referral/claim", methods=["POST"])
@jwt_required
def api_claim_referral():
    data = request.get_json() or {}
    code = data.get("code", "").strip().upper()
    if not code:
        return jsonify({"error": "codice richiesto"}), 400
    ok, msg = claim_referral_bonus(g.user_id, code)
    if not ok:
        return jsonify({"error": msg}), 400
    from storage import audit_log
    audit_log(g.user_id, "referral.claim", f"code={code}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify({"status": "ok", "bonus": 50})


# ─── Social Share ─────────────────────────────────────────────────

@app.route("/user/mevacoins/share", methods=["POST"])
@jwt_required
def api_social_share():
    data = request.get_json() or {}
    platform = data.get("platform", "")
    ok, msg = add_social_share(g.user_id, platform)
    if not ok:
        return jsonify({"error": msg}), 400 if msg == "limite_giornaliero" else 500
    from storage import audit_log
    audit_log(g.user_id, "mevacoins.share", f"platform={platform}", request.remote_addr or "", request.headers.get("User-Agent", ""))
    return jsonify({"status": "ok", "earned": 30})


@app.route("/user/mevacoins/share/status", methods=["GET"])
@jwt_required
def api_share_status():
    count = get_daily_share_count(g.user_id)
    return jsonify({"today_count": count, "max_daily": 3})


@app.route("/user/mevacoins/streak", methods=["GET"])
@jwt_required
def api_streak():
    streak = get_checkin_streak(g.user_id)
    return jsonify({"streak": streak})


@app.route("/chat/suggestion", methods=["POST"])
@jwt_required
def api_chat_suggestion():
    data = request.get_json()
    character_id = data.get("character_id", "")
    if not character_id:
        return jsonify({"error": "character_id required"}), 400
    
    from characters import get_character
    char = get_character(character_id)
    if not char:
        return jsonify({"error": "character not found"}), 404
    
    prefs = get_user_preferences(g.user_id)
    tags = prefs.get("interest_tags", [])
    tags_str = ", ".join(tags) if tags else "generali"
    
    prompt = (
        f"Genera UNA domanda o frase di apertura che l'utente potrebbe inviare al personaggio '{char['name']}' "
        f"per iniziare una conversazione interessante. "
        f"La domanda deve essere naturale, in italiano, e tenere conto che l'utente ha questi interessi: {tags_str}. "
        f"Il personaggio è: {char.get('essence', 'un personaggio virtuale')}. "
        f"Restituisci SOLO la domanda, senza prefazioni o spiegazioni."
    )
    
    from ai_engine import get_ai_response
    suggestion, _, _ = get_ai_response([
        {"role": "system", "content": "Sei un assistente che genera domande di apertura per chat con personaggi virtuali. Rispondi solo con la domanda, nient'altro."},
        {"role": "user", "content": prompt}
    ], user_id=g.user_id)
    
    if not suggestion:
        fallbacks = [
            f"Ciao {char['name']}! Come stai?",
            f"Raccontami qualcosa di te, {char['name']}.",
            f"Che cosa ti appassiona di più, {char['name']}?",
        ]
        import random
        suggestion = random.choice(fallbacks)
    
    return jsonify({"suggestion": suggestion.strip()})


def _free_port(port):
    import subprocess, signal
    try:
        own_pid, ppid = os.getpid(), os.getppid()
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split() if int(p) not in (own_pid, ppid)]
            if not pids:
                return
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

if __name__ == "__main__":
    logger.info("Initializing database...")
    init_db()
    init_auth_db()
    init_provider()
    port = int(os.environ.get("PORT", 5000))
    _free_port(port)
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()
    from auth import _cleanup_expired_tokens as _auth_cleanup
    token_cleanup = threading.Thread(target=_auth_cleanup, daemon=True)
    token_cleanup.start()
    logger.info(f"Starting on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
