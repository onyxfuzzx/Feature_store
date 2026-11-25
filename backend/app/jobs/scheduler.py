"""UTC cron dispatch with database locks and durable scheduled-minute deduplication."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from app.db.models.jobs import JobDefinition, JobRun
from app.db.session import SessionLocal, engine
from app.services.materialization import materialize_feature
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")


def _run_job(job_id, scheduled=False, scheduled_for=None):
    job_id = UUID(str(job_id))
    lock_key = job_id.int & ((1 << 63) - 1)
    slot = (
        (scheduled_for or datetime.now(UTC)).replace(second=0, microsecond=0) if scheduled else None
    )
    with engine.connect() as connection:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
        ).scalar_one()
        connection.commit()
        if not acquired:
            return None
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                job = db.get(JobDefinition, job_id)
                if not job or (scheduled and not job.is_active):
                    return None
                if (
                    scheduled
                    and CronTrigger.from_crontab(job.cron, timezone="UTC").get_next_fire_time(
                        None, slot
                    )
                    != slot
                ):
                    return None  # a different worker may not yet have refreshed an edited cron
                if (
                    slot
                    and db.query(JobRun)
                    .filter_by(job_definition_id=job_id, scheduled_for=slot)
                    .first()
                ):
                    return None
                # Acquiring the session lock proves any older running worker is gone.
                for abandoned in db.query(JobRun).filter_by(
                    job_definition_id=job_id, status="running"
                ):
                    abandoned.status = "failed"
                    abandoned.finished_at = datetime.now(UTC)
                    abandoned.log = "Worker disconnected before completing this run"
                run = JobRun(
                    job_definition_id=job.id,
                    status="running",
                    scheduled_for=slot,
                    started_at=datetime.now(UTC),
                )
                db.add(run)
                db.commit()
                run_id = run.id
                try:
                    if job.type != "feature_materialization":
                        raise ValueError(f"Unsupported job type: {job.type}")
                    feature_id = UUID(json.loads(job.payload_json or "{}")["feature_id"])
                    result = materialize_feature(db, feature_id)
                    if result.status != "success":
                        raise ValueError(result.error_message or "Feature materialization failed")
                    run.status = "success"
                except Exception as exc:
                    logger.exception("Job run failed")
                    db.rollback()
                    run = db.get(JobRun, run_id)
                    run.status = "failed"
                    run.log = str(exc)
                run.finished_at = datetime.now(UTC)
                db.commit()
                return run_id
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            connection.commit()


def schedule_job(job):
    if not job.is_active:
        if scheduler.get_job(str(job.id)):
            scheduler.remove_job(str(job.id))
        return
    trigger = CronTrigger.from_crontab(job.cron, timezone="UTC")
    existing = scheduler.get_job(str(job.id))
    if existing and str(existing.trigger) == str(trigger):
        return
    scheduler.add_job(
        _run_job,
        trigger=trigger,
        args=[job.id],
        kwargs={"scheduled": True},
        id=str(job.id),
        replace_existing=True,
        name=job.name,
        coalesce=True,
        misfire_grace_time=30,
    )


def sync_schedules():
    try:
        with SessionLocal() as db:
            jobs = db.query(JobDefinition).all()
            identities = {str(job.id) for job in jobs}
            for job in jobs:
                try:
                    schedule_job(job)
                except ValueError:
                    logger.exception("Invalid legacy schedule %s", job.id)
            for job in scheduler.get_jobs():
                if job.id != "__refresh__" and job.id not in identities:
                    scheduler.remove_job(job.id)
    except Exception:
        logger.exception("Could not refresh schedules")


def start_scheduler():
    if not scheduler.running:
        sync_schedules()
        scheduler.add_job(
            sync_schedules, "interval", seconds=5, id="__refresh__", replace_existing=True
        )
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
