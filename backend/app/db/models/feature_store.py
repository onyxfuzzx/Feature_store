import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class FeatureGroup(Base):
    __tablename__ = "feature_group"
    __table_args__ = (UniqueConstraint("environment", "name", name="uq_feature_group_scope"), {"schema": "feature_store"})

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True)
    tags_json = Column(Text, nullable=True)
    environment = Column(String(40), nullable=False, server_default=text("'dev'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureDefinition(Base):
    __tablename__ = "feature_definition"
    __table_args__ = (UniqueConstraint("group_id", "name", name="uq_feature_definition_scope"), {"schema": "feature_store"})

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    online_revision = Column(BigInteger, nullable=False, server_default=text("0"))
    group_id = Column(
        UUID(as_uuid=True), ForeignKey("feature_store.feature_group.id"), nullable=False
    )
    name = Column(String(120), nullable=False)
    dtype = Column(String(40), nullable=False)
    description = Column(String(500), nullable=True)
    source_sql = Column(Text, nullable=False)
    refresh_interval = Column(String(40), nullable=False)
    status = Column(String(40), nullable=False, server_default=text("'draft'"))
    validation_rules_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureLineage(Base):
    __tablename__ = "feature_lineage"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature_id = Column(
        UUID(as_uuid=True), ForeignKey("feature_store.feature_definition.id"), nullable=False
    )
    source_table = Column(String(200), nullable=False)
    source_columns_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureMaterialization(Base):
    __tablename__ = "feature_materialization"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature_id = Column(
        UUID(as_uuid=True), ForeignKey("feature_store.feature_definition.id"), nullable=False
    )
    status = Column(String(40), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    row_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class FeatureValueOnline(Base):
    __tablename__ = "feature_values_online"
    __table_args__ = {"schema": "feature_store"}

    entity_key = Column(String(120), primary_key=True)
    feature_id = Column(
        UUID(as_uuid=True), ForeignKey("feature_store.feature_definition.id"), primary_key=True
    )
    value = Column(Text, nullable=True)
    event_time = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeatureValueOffline(Base):
    __tablename__ = "feature_values_offline"
    __table_args__ = {"schema": "feature_store"}

    entity_key = Column(String(120), primary_key=True)
    feature_id = Column(
        UUID(as_uuid=True), ForeignKey("feature_store.feature_definition.id"), primary_key=True
    )
    event_time = Column(DateTime(timezone=True), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
