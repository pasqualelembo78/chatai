from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from characters import get_character
from storage import (
    get_user_memory, update_user_memory, reset_user_memory,
    get_evolution,
)
from auth_fastapi import jwt_required, AuthUser

router = APIRouter()


class MemoryUpdateRequest(BaseModel):
    facts: dict = {}


@router.get("/memory")
async def api_get_memory(user: AuthUser = Depends(jwt_required)):
    return get_user_memory(user.user_id)


@router.post("/memory")
async def api_update_memory(body: MemoryUpdateRequest, user: AuthUser = Depends(jwt_required)):
    if not body.facts:
        raise HTTPException(400, "facts required")
    memory = update_user_memory(user.user_id, body.facts)
    return {"status": "ok", "memory": memory}


@router.delete("/memory")
async def api_reset_memory(user: AuthUser = Depends(jwt_required)):
    reset_user_memory(user.user_id)
    return {"status": "memory_reset"}


@router.get("/evolution")
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
