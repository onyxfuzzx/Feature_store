from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase
from pydantic import Field, field_validator


class UserCreate(ORMBase):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12)
    roles: list[str]

    @field_validator("password")
    @classmethod
    def bcrypt_length(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit bcrypt's 72-byte limit")
        return value


class UserOut(ORMBase):
    id: UUID
    name: str
    email: str
    is_active: bool
    roles: list[str]
    created_at: datetime
