from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase


class FeatureGroupCreate(ORMBase):
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    tags_json: str | None = None
    environment: str = "dev"


class FeatureGroupOut(ORMBase):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    tags_json: str | None = None
    environment: str
    created_at: datetime


class FeatureDefinitionCreate(ORMBase):
    group_id: UUID
    name: str
    dtype: str
    description: str | None = None
    source_sql: str
    refresh_interval: str
    status: str = "draft"
    validation_rules_json: str | None = None


class FeatureDefinitionOut(ORMBase):
    id: UUID
    group_id: UUID
    name: str
    dtype: str
    description: str | None = None
    source_sql: str
    refresh_interval: str
    status: str
    validation_rules_json: str | None = None
    created_at: datetime


class FeatureMaterializationOut(ORMBase):
    id: UUID
    feature_id: UUID
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    row_count: int | None = None
    error_message: str | None = None


class FeatureLineageCreate(ORMBase):
    source_table: str
    source_columns_json: str | None = None


class FeatureLineageOut(ORMBase):
    id: UUID
    feature_id: UUID
    source_table: str
    source_columns_json: str | None = None
    created_at: datetime


class FeatureValueOut(ORMBase):
    entity_key: str
    feature_id: UUID
    value: str | None = None
    event_time: datetime | None = None
    updated_at: datetime


class FeatureDefinitionUpdate(ORMBase):
    description: str | None = None
    status: str | None = None
    refresh_interval: str | None = None
    validation_rules_json: str | None = None


class BatchOnlineFeaturesRequest(ORMBase):
    entity_keys: list[str]
    features: list[str]  # feature IDs or names (e.g. 'customer_30d_spend' or 'group:name')


class BatchOnlineFeaturesResponse(ORMBase):
    entity_keys: list[str]
    features: list[str]
    values: dict[str, dict[str, str | None]]  # entity_key -> {feature_name: value}
    read_latency_ms: float


class AsOfJoinObservation(ORMBase):
    entity_key: str
    event_time: datetime


class AsOfJoinRequest(ORMBase):
    observations: list[AsOfJoinObservation]
    features: list[str]  # feature IDs or names


class AsOfJoinResponse(ORMBase):
    joined_rows: list[dict[str, str | None]]
    row_count: int
    computation_time_ms: float


class StreamIngestRecord(ORMBase):
    entity_key: str
    feature_id: UUID | None = None
    feature_name: str | None = None
    value: str | None = None
    event_time: datetime | None = None


class StreamIngestRequest(ORMBase):
    records: list[StreamIngestRecord]
    persist_offline: bool = True


class StreamIngestResponse(ORMBase):
    ingested_count: int
    success: bool
    timestamp: datetime



