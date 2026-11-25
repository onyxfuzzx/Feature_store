from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import ORMBase
from pydantic import Field, field_validator


class ModelCreate(ORMBase):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    owner_id: UUID | None = None
    environment: str = Field(
        default="dev", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$"
    )


class ModelOut(ORMBase):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    environment: str
    created_at: datetime


class ModelVersionCreate(ORMBase):
    version: str = Field(min_length=1, max_length=40)
    stage: Literal["Staging", "Production", "Archived"] = "Staging"
    metrics_json: str | None = None
    params_json: str | None = None
    artifact_uri: str | None = None

    @field_validator("artifact_uri")
    @classmethod
    def require_upload(cls, value):
        if value is not None:
            raise ValueError(
                "Use the artifact upload endpoint; arbitrary artifact URIs are not accepted"
            )
        return value


class ModelVersionOut(ORMBase):
    id: UUID
    model_id: UUID
    version: str
    stage: str
    metrics_json: str | None = None
    params_json: str | None = None
    artifact_uri: str | None = None
    created_at: datetime


class ModelStageHistoryOut(ORMBase):
    id: UUID
    model_version_id: UUID
    from_stage: str
    to_stage: str
    changed_by: UUID | None = None
    changed_at: datetime


class ModelLineageCreate(ORMBase):
    feature_ids_json: str | None = None
    dataset_uri: str | None = None


class ModelLineageOut(ORMBase):
    id: UUID
    model_version_id: UUID
    feature_ids_json: str | None = None
    dataset_uri: str | None = None
    created_at: datetime


class ModelVersionDetailOut(ModelVersionOut):
    lineage: list[ModelLineageOut] = []
    stage_history: list[ModelStageHistoryOut] = []


class ModelHydrateRequest(ORMBase):
    entity_keys: list[str] = Field(min_length=1, max_length=1000)
    version: str | None = None  # None = active Production / latest version


class ModelHydrateResponse(ORMBase):
    model_id: UUID
    version: str
    features: list[str]
    hydrated_records: list[dict[str, str | None]]
    latency_ms: float


class ModelPredictRequest(ORMBase):
    entity_key: str = Field(min_length=1, max_length=120)
    version: str | None = None
    runtime_features: dict[str, str | float] = {}


class ModelPredictResponse(ORMBase):
    model_id: UUID
    version: str
    entity_key: str
    features_used: dict[str, str | None]
    prediction: dict
    latency_ms: float
