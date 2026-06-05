from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMBase


class JobDefinitionCreate(ORMBase):
    name: str
    type: str
    cron: str
    payload_json: str | None = None
    is_active: bool = True


class JobDefinitionOut(ORMBase):
    id: UUID
    name: str
    type: str
    cron: str
    payload_json: str | None = None
    is_active: bool
    created_at: datetime


class JobRunOut(ORMBase):
    id: UUID
    job_definition_id: UUID
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    log: str | None = None
