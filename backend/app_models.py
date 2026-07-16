from typing import Optional
from pydantic import BaseModel


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


class AdminDmRequest(BaseModel):
    content: str
