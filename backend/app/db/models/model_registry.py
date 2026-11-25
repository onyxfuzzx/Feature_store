import uuid

from app.db.base_class import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func


class Model(Base):
    __tablename__ = "model"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True)
    environment = Column(String(40), nullable=False, server_default=text("'dev'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_version"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_version_identity"),
        CheckConstraint(
            "stage IN ('Staging', 'Production', 'Archived')", name="ck_model_version_stage"
        ),
        Index(
            "uq_model_one_production",
            "model_id",
            unique=True,
            postgresql_where=text("stage = 'Production'"),
        ),
        {"schema": "model_registry"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_registry.model.id"), nullable=False)
    version = Column(String(40), nullable=False)
    stage = Column(String(40), nullable=False, server_default=text("'Staging'"))
    metrics_json = Column(Text, nullable=True)
    params_json = Column(Text, nullable=True)
    artifact_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelLineage(Base):
    __tablename__ = "model_lineage"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
    )
    feature_ids_json = Column(Text, nullable=True)
    dataset_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelStageHistory(Base):
    __tablename__ = "model_stage_history"
    __table_args__ = {"schema": "model_registry"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
    )
    from_stage = Column(String(40), nullable=False)
    to_stage = Column(String(40), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DriftBaseline(Base):
    __tablename__ = "drift_baseline"
    __table_args__ = {"schema": "model_registry"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
        index=True,
    )
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    distributions = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class InferenceObservation(Base):
    __tablename__ = "inference_observation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("model_registry.model_version.id"), nullable=False
    )
    entity_key = Column(String(120), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    values_json = Column(JSONB, nullable=False)
    __table_args__ = (
        Index("ix_inference_version_time", "model_version_id", "observed_at"),
        {"schema": "model_registry"},
    )


class DriftRun(Base):
    __tablename__ = "drift_run"
    __table_args__ = {"schema": "model_registry"}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("model_registry.model_version.id"),
        nullable=False,
        index=True,
    )
    baseline_id = Column(
        UUID(as_uuid=True), ForeignKey("model_registry.drift_baseline.id"), nullable=True
    )
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(40), nullable=False)
    result_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
