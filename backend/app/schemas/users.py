from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase


class UserCreate(ORMBase):
    name: str
    email: str
    password: str
    roles: list[str]


class UserOut(ORMBase):
    id: UUID
    name: str
    email: str
    is_active: bool
    roles: list[str]
    created_at: datetime
