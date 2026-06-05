import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.sql import func

from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "core"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    name = Column(String(80), nullable=False, unique=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("core.users.id"),
        primary_key=True,
        nullable=False,
    )
    role_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("core.roles.id"),
        primary_key=True,
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "core"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    actor_id = Column(UNIQUEIDENTIFIER, ForeignKey("core.users.id"), nullable=True)
    action = Column(String(120), nullable=False)
    entity_type = Column(String(120), nullable=False)
    entity_id = Column(String(120), nullable=False)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class APIKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "core"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    user_id = Column(UNIQUEIDENTIFIER, ForeignKey("core.users.id"), nullable=False)
    name = Column(String(120), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())
