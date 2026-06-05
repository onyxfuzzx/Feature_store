import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.sql import func

from app.db.base_class import Base


class FeatureGroup(Base):
    __tablename__ = "feature_group"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    owner_id = Column(UNIQUEIDENTIFIER, ForeignKey("core.users.id"), nullable=True)
    tags_json = Column(Text, nullable=True)
    environment = Column(String(40), nullable=False, server_default=text("'dev'"))
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class FeatureDefinition(Base):
    __tablename__ = "feature_definition"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    group_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("feature_store.feature_group.id"), nullable=False
    )
    name = Column(String(120), nullable=False)
    dtype = Column(String(40), nullable=False)
    description = Column(String(500), nullable=True)
    source_sql = Column(Text, nullable=False)
    refresh_interval = Column(String(40), nullable=False)
    status = Column(String(40), nullable=False, server_default=text("'draft'"))
    validation_rules_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class FeatureLineage(Base):
    __tablename__ = "feature_lineage"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    feature_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("feature_store.feature_definition.id"), nullable=False
    )
    source_table = Column(String(200), nullable=False)
    source_columns_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class FeatureMaterialization(Base):
    __tablename__ = "feature_materialization"
    __table_args__ = {"schema": "feature_store"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    feature_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("feature_store.feature_definition.id"), nullable=False
    )
    status = Column(String(40), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    row_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class FeatureValueOnline(Base):
    __tablename__ = "feature_values_online"
    __table_args__ = {"schema": "feature_store"}

    entity_key = Column(String(120), primary_key=True)
    feature_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("feature_store.feature_definition.id"), primary_key=True
    )
    value = Column(Text, nullable=True)
    event_time = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class FeatureValueOffline(Base):
    __tablename__ = "feature_values_offline"
    __table_args__ = {"schema": "feature_store"}

    entity_key = Column(String(120), primary_key=True)
    feature_id = Column(
        UNIQUEIDENTIFIER, ForeignKey("feature_store.feature_definition.id"), primary_key=True
    )
    event_time = Column(DateTime, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())
