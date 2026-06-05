import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.sql import func

from app.db.base_class import Base


class JobDefinition(Base):
    __tablename__ = "job_definition"
    __table_args__ = {"schema": "jobs"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    type = Column(String(60), nullable=False)
    cron = Column(String(60), nullable=False)
    payload_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.sysutcdatetime())


class JobRun(Base):
    __tablename__ = "job_run"
    __table_args__ = {"schema": "jobs"}

    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    job_definition_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("jobs.job_definition.id"),
        nullable=False,
    )
    status = Column(String(40), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    log = Column(Text, nullable=True)
