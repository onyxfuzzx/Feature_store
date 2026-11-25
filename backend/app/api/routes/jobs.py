import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles, get_current_user
from app.core import roles
from app.db.models.core import User
from app.db.models.jobs import JobDefinition, JobRun
from app.db.models.feature_store import FeatureDefinition
from app.db.session import get_db
from app.jobs.scheduler import _run_job, schedule_job
from app.schemas.jobs import JobDefinitionCreate, JobDefinitionOut, JobOverviewItem, JobRunOut
from app.services.audit import log_audit

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=list[JobDefinitionOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def list_jobs(db: Session = Depends(get_db)):
    return db.query(JobDefinition).order_by(JobDefinition.created_at.desc()).all()


@router.get(
    "/overview",
    response_model=list[JobOverviewItem],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def get_jobs_overview(db: Session = Depends(get_db)):
    jobs = db.query(JobDefinition).order_by(JobDefinition.created_at.desc()).all()
    results = []
    for job in jobs:
        runs = (
            db.query(JobRun)
            .filter(JobRun.job_definition_id == job.id)
            .order_by(JobRun.started_at.desc())
            .limit(5)
            .all()
        )
        results.append(
            JobOverviewItem(
                id=job.id,
                name=job.name,
                type=job.type,
                cron=job.cron,
                payload_json=job.payload_json,
                is_active=job.is_active,
                created_at=job.created_at,
                recent_runs=runs,
            )
        )
    return results


@router.post(
    "",
    response_model=JobDefinitionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def create_job(payload: JobDefinitionCreate, db: Session = Depends(get_db)):
    if not db.get(FeatureDefinition, UUID(json.loads(payload.payload_json)["feature_id"])):
        raise HTTPException(422, "Job feature does not exist")
    job = JobDefinition(
        name=payload.name,
        type=payload.type,
        cron=payload.cron,
        payload_json=payload.payload_json,
        is_active=payload.is_active,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if job.is_active:
        schedule_job(job)

    return job


@router.post(
    "/{job_id}/run",
    response_model=JobRunOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def run_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    run_id = _run_job(job.id)
    if run_id is None:
        raise HTTPException(409, "Job is already running; another worker owns its execution lock")
    run = db.get(JobRun, run_id)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="RUN_JOB",
        entity_type="job_definition",
        entity_id=job.id,
        payload={"job_name": job.name, "run_id": str(run.id), "status": run.status},
    )

    return run


@router.get(
    "/{job_id}/runs",
    response_model=list[JobRunOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def list_job_runs(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return (
        db.query(JobRun)
        .filter(JobRun.job_definition_id == job.id)
        .order_by(JobRun.started_at.desc())
        .all()
    )


@router.put("/{job_id}", response_model=JobDefinitionOut,
            dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))])
def update_job(job_id: UUID, payload: JobDefinitionCreate, db: Session = Depends(get_db)):
    job = db.get(JobDefinition, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not db.get(FeatureDefinition, UUID(json.loads(payload.payload_json)["feature_id"])):
        raise HTTPException(422, "Job feature does not exist")
    for key, value in payload.model_dump().items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    schedule_job(job)
    return job
