import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.sql import func

from app.db.base_class import Base


class Model(Base):
    __tablename__ = "model"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    owner_id = Column(UNIQUEIDENTIFIER, ForeignKey("core.users.id"), nullable=True)
    environment = Column(String(40), nullable=False, server_default=text("'dev'"))
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class ModelVersion(Base):
    __tablename__ = "model_version"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    model_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("model_registry.model.id"), nullable=False
    )
    version = Column(String(40), nullable=False)
    stage = Column(String(40), nullable=False, server_default=text("'Staging'"))
    metrics_json = Column(Text, nullable=True)
    params_json = Column(Text, nullable=True)
    artifact_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class ModelLineage(Base):
    __tablename__ = "model_lineage"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
    )
    feature_ids_json = Column(Text, nullable=True)
    dataset_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class ModelStageHistory(Base):
    __tablename__ = "model_stage_history"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
    )
    from_stage = Column(String(40), nullable=False)
    to_stage = Column(String(40), nullable=False)
    changed_by = Column(UNIQUEIDENTIFIER, ForeignKey("core.users.id"), nullable=True)
    changed_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())
