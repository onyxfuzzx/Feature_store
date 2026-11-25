from datetime import datetime, timezone
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from app.services.validation import parse_rules

from app.schemas.common import ORMBase


class FeatureGroupCreate(ORMBase):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[^/:]+$")
    description: str | None = None
    owner_id: UUID | None = None
    tags_json: str | None = None
    environment: str = Field(default="dev", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


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
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    dtype: str
    description: str | None = None
    source_sql: str
    refresh_interval: str
    status: str = "draft"
    validation_rules_json: str | None = None

    @field_validator("validation_rules_json")
    @classmethod
    def validate_rules(cls, value):
        parse_rules(value)
        return value


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

    @field_validator("validation_rules_json")
    @classmethod
    def validate_rules(cls, value):
        parse_rules(value)
        return value


class BatchOnlineFeaturesRequest(ORMBase):
    entity_keys: list[str] = Field(min_length=1, max_length=1000)
    features: list[str] = Field(min_length=1, max_length=100)
    environment: str | None = None


class BatchOnlineFeaturesResponse(ORMBase):
    entity_keys: list[str]
    features: list[str]
    values: dict[str, dict[str, str | None]]  # entity_key -> {feature_name: value}
    read_latency_ms: float


class AsOfJoinObservation(ORMBase):
    entity_key: str
    event_time: datetime

    @field_validator("event_time")
    @classmethod
    def normalize_time(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AsOfJoinRequest(ORMBase):
    observations: list[AsOfJoinObservation] = Field(min_length=1, max_length=1000)
    features: list[str] = Field(min_length=1, max_length=100)
    environment: str | None = None

    @model_validator(mode="after")
    def bounded_join(self):
        if len(self.observations) * len(self.features) > 10000:
            raise ValueError("Join request exceeds 10000 feature-observation pairs")
        return self


class AsOfJoinResponse(ORMBase):
    joined_rows: list[dict[str, str | None]]
    row_count: int
    computation_time_ms: float


class StreamIngestRecord(ORMBase):
    entity_key: str = Field(min_length=1, max_length=120)
    feature_id: UUID | None = None
    feature_name: str | None = None
    value: str | None = None
    event_time: datetime | None = None

    @field_validator("event_time")
    @classmethod
    def normalize_time(cls, value):
        return AsOfJoinObservation.normalize_time(value) if value else None

    @model_validator(mode="after")
    def one_feature_reference(self):
        if bool(self.feature_id) == bool(self.feature_name):
            raise ValueError("Provide exactly one feature_id or feature_name")
        return self


class StreamIngestRequest(ORMBase):
    records: list[StreamIngestRecord] = Field(min_length=1, max_length=10000)
    persist_offline: bool = True
    environment: str | None = None


class StreamIngestResponse(ORMBase):
    ingested_count: int
    online_updated_count: int = 0
    success: bool
    timestamp: datetime


class QueryDryRunRequest(ORMBase):
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class QueryDryRunResponse(ORMBase):
    columns: list[str] = []
    rows: list[dict[str, str | None]] = []
    row_count: int = 0
    execution_time_ms: float = 0.0
    is_valid: bool = True
    error: str | None = None


class LineageNode(ORMBase):
    id: str
    label: str
    type: str  # source_table, feature_group, feature, model, endpoint
    metadata: dict[str, str | None] = {}


class LineageEdge(ORMBase):
    source: str
    target: str
    label: str | None = None


class LineageGraphOut(ORMBase):
    nodes: list[LineageNode] = []
    edges: list[LineageEdge] = []



