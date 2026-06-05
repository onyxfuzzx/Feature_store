from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase


class ModelCreate(ORMBase):
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    environment: str = "dev"


class ModelOut(ORMBase):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    environment: str
    created_at: datetime


class ModelVersionCreate(ORMBase):
    version: str
    stage: str = "Staging"
    metrics_json: str | None = None
    params_json: str | None = None
    artifact_uri: str | None = None


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

