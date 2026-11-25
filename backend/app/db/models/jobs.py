import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class JobDefinition(Base):
    __tablename__ = "job_definition"
    __table_args__ = {"schema": "jobs"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    type = Column(String(60), nullable=False)
    cron = Column(String(60), nullable=False)
    payload_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_run"
    __table_args__ = (UniqueConstraint("job_definition_id", "scheduled_for", name="uq_job_scheduled_slot"), {"schema": "jobs"})

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_definition.id"),
        nullable=False,
    )
    status = Column(String(40), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    log = Column(Text, nullable=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
