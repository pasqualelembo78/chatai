from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from auth_fastapi import jwt_required, AuthUser
from storage import block_user, unblock_user, get_blocked_users, is_blocked

router = APIRouter()


class BlockRequest(BaseModel):
    blocked_id: str


@router.get("/users/blocked")
async def api_get_blocked(user: AuthUser = Depends(jwt_required)):
    return {"blocked": get_blocked_users(user.user_id)}


@router.post("/users/block")
async def api_block_user(req: BlockRequest, user: AuthUser = Depends(jwt_required)):
    if not req.blocked_id:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="blocked_id richiesto")
    ok = block_user(user.user_id, req.blocked_id)
    if not ok:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Impossibile bloccare l'utente")
    return {"status": "blocked", "blocked_id": req.blocked_id}


@router.delete("/users/block/{blocked_id}")
async def api_unblock_user(blocked_id: str, user: AuthUser = Depends(jwt_required)):
    unblock_user(user.user_id, blocked_id)
    return {"status": "unblocked", "blocked_id": blocked_id}


@router.get("/users/is-blocked/{other_id}")
async def api_is_blocked(other_id: str, user: AuthUser = Depends(jwt_required)):
    return {"blocked": is_blocked(user.user_id, other_id)}
