from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase

class APIKeyCreate(ORMBase):
    name: str

class APIKeyOut(ORMBase):
    id: UUID
    user_id: UUID
    name: str
    is_active: bool
    created_at: datetime

class APIKeyCreateOut(APIKeyOut):
    plain_key: str  # Only returned once upon creation
