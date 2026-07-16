from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from characters import get_character
from storage import (
    get_recent_messages, reset_conversation, reset_all_user_data,
    audit_log,
)
from db import get_conn, put_conn
from auth_fastapi import jwt_required, AuthUser

router = APIRouter()


class ReportRequest(BaseModel):
    reported_user: str = "unknown"
    character_id: str = ""
    message_text: str = ""


@router.get("/conversations")
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


@router.get("/conversations/{character_id}")
async def api_get_conversation(character_id: str, user: AuthUser = Depends(jwt_required)):
    msgs = get_recent_messages(user.user_id, character_id, limit=1000)
    return {"character_id": character_id, "messages": msgs}


@router.post("/conversations/{character_id}/reset")
async def api_reset_conversation(character_id: str, user: AuthUser = Depends(jwt_required)):
    reset_conversation(user.user_id, character_id)
    return {"status": "conversation_reset", "character_id": character_id}


@router.post("/user/reset")
async def api_reset_user(user: AuthUser = Depends(jwt_required)):
    reset_all_user_data(user.user_id)
    return {"status": "all_data_reset"}


@router.get("/user/export")
async def api_export_user(request: Request, user: AuthUser = Depends(jwt_required)):
    from storage import export_user_data
    data = export_user_data(user.user_id)
    audit_log(user.user_id, "user.export", "exported all data",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    return data


@router.post("/user/delete")
async def api_delete_user(request: Request, user: AuthUser = Depends(jwt_required)):
    from storage import delete_user
    audit_log(user.user_id, "user.delete", "account deleted",
              request.client.host if request.client else "",
              request.headers.get("User-Agent", ""))
    delete_user(user.user_id)
    return {"status": "account_deleted"}


@router.post("/user/report")
async def api_user_report(request: Request, body: ReportRequest, user: AuthUser = Depends(jwt_required)):
    from storage import flag_user
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
