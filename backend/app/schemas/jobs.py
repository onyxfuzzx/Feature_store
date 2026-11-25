from datetime import datetime
from uuid import UUID
from typing import Literal
import json
from pydantic import Field, field_validator
from apscheduler.triggers.cron import CronTrigger

from app.schemas.common import ORMBase


class JobDefinitionCreate(ORMBase):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["feature_materialization"]
    cron: str
    payload_json: str
    is_active: bool = True

    @field_validator("cron")
    @classmethod
    def valid_cron(cls, value):
        CronTrigger.from_crontab(value, timezone="UTC")
        return value

    @field_validator("payload_json")
    @classmethod
    def valid_payload(cls, value):
        payload = json.loads(value or "{}")
        if not isinstance(payload, dict) or set(payload) != {"feature_id"}:
            raise ValueError("Job payload must contain exactly feature_id")
        payload["feature_id"] = str(UUID(str(payload["feature_id"])))
        return json.dumps(payload)


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


class JobOverviewItem(JobDefinitionOut):
    recent_runs: list[JobRunOut] = []

