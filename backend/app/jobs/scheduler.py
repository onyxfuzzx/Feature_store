import json
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.models.jobs import JobDefinition, JobRun
from app.db.session import SessionLocal
from app.services.materialization import materialize_feature

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_job(job_id):
    db: Session = SessionLocal()
    run = None
    try:
        job = db.get(JobDefinition, job_id)
        if not job or not job.is_active:
            return

        run = JobRun(
            job_definition_id=job.id,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        if job.type == "feature_materialization":
            payload = json.loads(job.payload_json or "{}")
            feature_id = payload.get("feature_id")
            if not feature_id:
                raise ValueError("Job payload missing feature_id")
            materialization = materialize_feature(db, feature_id)
            if materialization.status != "success":
                raise ValueError(materialization.error_message or "Feature materialization failed")
        else:
            raise ValueError(f"Unsupported job type: {job.type}")

        run.status = "success"
    except Exception as exc:
        logger.exception("Job run failed")
        if run:
            run.status = "failed"
            run.log = str(exc)
    finally:
        if run:
            run.finished_at = datetime.utcnow()
            db.commit()
        db.close()


def schedule_job(job: JobDefinition) -> None:
    try:
        trigger = CronTrigger.from_crontab(job.cron)
    except ValueError as exc:
        logger.warning("Invalid cron for job %s: %s", job.id, exc)
        return

    scheduler.add_job(
        _run_job,
        trigger=trigger,
        args=[job.id],
        id=str(job.id),
        replace_existing=True,
        name=job.name,
    )


def start_scheduler() -> None:
    if scheduler.running:
        return

    db = SessionLocal()
    try:
        jobs = db.query(JobDefinition).filter(JobDefinition.is_active == True).all()
        for job in jobs:
            schedule_job(job)
    except Exception:
        logger.exception("Failed to load job schedule")
    finally:
        db.close()

    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
