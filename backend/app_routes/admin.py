import re
import uuid
from typing import Optional

from fastapi import APIRouter, Request, Query, Depends, HTTPException
from pydantic import BaseModel

from characters import get_character
from storage import (
    get_all_users, ban_user, prune_old_data,
    get_moderation_flags, resolve_moderation_flag,
    get_admin_stats, search_users, get_user_detail,
    update_user_role, get_all_user_characters, delete_user_character,
    list_user_conversations, get_user_conversation_messages,
    send_admin_dm, list_admin_dms, mark_admin_dms_read,
    create_user_character, init_new_user_bonus,
    audit_log,
)
from db import get_conn, put_conn
from auth_fastapi import admin_required, AuthUser, generate_password_hash

router = APIRouter(prefix="/admin")


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


class AvatarGenRequest(BaseModel):
    limit: int = 50
    force: bool = False


class RoleRequest(BaseModel):
    role: str = "user"


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    role: str = "user"


class AdminDmRequest(BaseModel):
    content: str


@router.get("/users")
async def admin_list_users(user: AuthUser = Depends(admin_required)):
    return get_all_users()


@router.post("/ban")
async def admin_ban_user(request: Request, body: BanRequest, user: AuthUser = Depends(admin_required)):
    if not body.user_id:
        raise HTTPException(400, "user_id richiesto")
    ban_user(body.user_id, body.hours)
    detail = f"banned for {body.hours}h" if body.hours > 0 else "unbanned"
    audit_log(user.user_id, "admin.ban", f"user={body.user_id} {detail}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "detail": detail}


@router.post("/prune")
async def admin_prune(request: Request, body: PruneRequest, user: AuthUser = Depends(admin_required)):
    result = prune_old_data(body.days)
    audit_log(user.user_id, "admin.prune", f"days={body.days} result={result}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "pruned": result}


@router.get("/logs")
async def admin_logs(limit: int = Query(100), user: AuthUser = Depends(admin_required)):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (min(limit, 1000),))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        put_conn(conn)


@router.get("/flags")
async def admin_flags(resolved: str = Query("false"), user: AuthUser = Depends(admin_required)):
    return get_moderation_flags(resolved=resolved.lower() == "true")


@router.post("/flags/{flag_id}/resolve")
async def admin_resolve_flag(flag_id: int, request: Request, user: AuthUser = Depends(admin_required)):
    resolve_moderation_flag(flag_id)
    audit_log(user.user_id, "admin.resolve_flag", f"flag_id={flag_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "resolved", "flag_id": flag_id}


@router.get("/import/sources")
async def admin_import_sources(user: AuthUser = Depends(admin_required)):
    from import_engine import SOURCES
    return list(SOURCES.values())


@router.post("/import/start")
async def admin_import_start(request: Request, body: ImportRequest, user: AuthUser = Depends(admin_required)):
    from import_engine import start_import
    result = start_import(body.source, count=min(body.count, 16000), genre_filter=body.genre, filepath=body.filepath)
    if "error" in result:
        raise HTTPException(400, result["error"])
    audit_log(user.user_id, "admin.import_start", f"source={body.source} count={body.count}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result


@router.get("/import/status")
async def admin_import_status(user: AuthUser = Depends(admin_required)):
    from import_engine import get_import_status
    return get_import_status()


@router.get("/duplicates")
async def admin_duplicates(filepath: str = Query("backend/characters.py"), user: AuthUser = Depends(admin_required)):
    from import_engine import find_duplicates
    duplicates = find_duplicates(filepath)
    return {"total_duplicates": len(duplicates), "duplicates": duplicates[:100]}


@router.post("/duplicates/clean")
async def admin_clean_duplicates(request: Request, body: DuplicatesRequest, user: AuthUser = Depends(admin_required)):
    from import_engine import clean_duplicates
    result = clean_duplicates(body.filepath)
    audit_log(user.user_id, "admin.clean_duplicates", f"result={result}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result


@router.post("/avatars/generate")
async def admin_avatars_generate(request: Request, body: AvatarGenRequest, user: AuthUser = Depends(admin_required)):
    from avatar_gen_runner import start_avatar_generation
    result = start_avatar_generation(limit=body.limit, force=body.force)
    if "error" in result:
        raise HTTPException(400, result["error"])
    audit_log(user.user_id, "admin.avatars_generate", f"limit={body.limit} force={body.force}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result


@router.get("/avatars/status")
async def admin_avatars_status(user: AuthUser = Depends(admin_required)):
    from avatar_gen_runner import get_avatar_status
    return get_avatar_status()


@router.post("/avatars/stop")
async def admin_avatars_stop(request: Request, user: AuthUser = Depends(admin_required)):
    from avatar_gen_runner import stop_avatar_generation
    result = stop_avatar_generation()
    audit_log(user.user_id, "admin.avatars_stop", f"result={result.get('status')}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return result


@router.get("/stats")
async def admin_stats(user: AuthUser = Depends(admin_required)):
    return get_admin_stats()


@router.get("/users/search")
async def admin_search_users(q: str = Query(""), user: AuthUser = Depends(admin_required)):
    if not q:
        return []
    return search_users(q)


@router.get("/users/{user_id}")
async def admin_user_detail(user_id: str, user: AuthUser = Depends(admin_required)):
    detail = get_user_detail(user_id)
    if not detail:
        raise HTTPException(404, "Utente non trovato")
    return detail


@router.put("/users/{user_id}/role")
async def admin_update_role(user_id: str, request: Request, body: RoleRequest, user: AuthUser = Depends(admin_required)):
    if body.role not in ("user", "moderator", "admin"):
        raise HTTPException(400, "Ruolo non valido")
    ok = update_user_role(user_id, body.role)
    if not ok:
        raise HTTPException(404, "Utente non trovato")
    audit_log(user.user_id, "admin.role_change", f"user={user_id} role={body.role}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "user_id": user_id, "role": body.role}


@router.post("/users")
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
    audit_log(user.user_id, "admin.create_user", f"username={username} role={role}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "user_id": new_id, "username": username, "role": role}


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request, user: AuthUser = Depends(admin_required)):
    from storage import delete_user
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


@router.get("/characters")
async def admin_list_characters(user: AuthUser = Depends(admin_required)):
    chars = get_all_user_characters()
    return [{"id": c.get("id"), "name": c.get("name"), "category": c.get("category"),
             "user_id": c.get("user_id"), "is_adult": c.get("is_adult", False),
             "created_at": c.get("created_at")} for c in chars]


@router.delete("/characters/{char_id}")
async def admin_delete_character(char_id: str, request: Request, user: AuthUser = Depends(admin_required)):
    delete_user_character(char_id)
    audit_log(user.user_id, "admin.delete_character", f"char_id={char_id}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "deleted": char_id}


@router.get("/users/{user_id}/conversations")
async def admin_user_conversations(user_id: str, user: AuthUser = Depends(admin_required)):
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


@router.get("/users/{user_id}/conversations/{character_id}")
async def admin_user_conversation_messages(user_id: str, character_id: str, user: AuthUser = Depends(admin_required)):
    msgs = get_user_conversation_messages(user_id, character_id)
    return [{"role": m["role"], "content": m["content"],
             "timestamp": str(m["timestamp"]) if m.get("timestamp") else None} for m in msgs]


@router.post("/users/{user_id}/dm")
async def admin_send_dm(user_id: str, request: Request, body: AdminDmRequest, user: AuthUser = Depends(admin_required)):
    if not body.content.strip():
        raise HTTPException(400, "Messaggio vuoto")
    dm = send_admin_dm(user.user_id, user_id, body.content.strip())
    audit_log(user.user_id, "admin.send_dm", f"to={user_id} len={len(body.content)}",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return {"status": "ok", "id": dm["id"], "created_at": str(dm["created_at"])}


@router.get("/users/{user_id}/dms")
async def admin_list_dms(user_id: str, user: AuthUser = Depends(admin_required)):
    return list_admin_dms(user_id)


@router.post("/users/{user_id}/dms/read")
async def admin_mark_dms_read(user_id: str, user: AuthUser = Depends(admin_required)):
    count = mark_admin_dms_read(user_id)
    return {"marked_read": count}
