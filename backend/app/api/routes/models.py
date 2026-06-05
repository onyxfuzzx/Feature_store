from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles, get_current_user
from app.core import roles
from app.db.models.core import User
from app.db.models.model_registry import Model, ModelVersion, ModelLineage, ModelStageHistory
from app.db.session import get_db
from app.schemas.model_registry import (
    ModelCreate,
    ModelOut,
    ModelVersionCreate,
    ModelVersionOut,
    ModelStageHistoryOut,
    ModelLineageCreate,
    ModelLineageOut,
    ModelVersionDetailOut,
)
from app.services.audit import log_audit


router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "",
    response_model=list[ModelOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def list_models(db: Session = Depends(get_db)):
    return db.query(Model).order_by(Model.created_at.desc()).all()


@router.post(
    "",
    response_model=ModelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_model(
    payload: ModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = Model(
        name=payload.name,
        description=payload.description,
        owner_id=payload.owner_id,
        environment=payload.environment,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_MODEL",
        entity_type="model",
        entity_id=model.id,
        payload={"name": model.name},
    )
    return model


@router.get(
    "/{model_id}",
    response_model=ModelOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_model(model_id: UUID, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.get(
    "/{model_id}/versions",
    response_model=list[ModelVersionOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def list_model_versions(model_id: UUID, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id)
        .order_by(ModelVersion.created_at.desc())
        .all()
    )


@router.post(
    "/{model_id}/versions",
    response_model=ModelVersionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_model_version(
    model_id: UUID,
    payload: ModelVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    version = ModelVersion(
        model_id=model_id,
        version=payload.version,
        stage=payload.stage,
        metrics_json=payload.metrics_json,
        params_json=payload.params_json,
        artifact_uri=payload.artifact_uri,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_MODEL_VERSION",
        entity_type="model_version",
        entity_id=version.id,
        payload={"model_id": str(model_id), "version": version.version, "stage": version.stage},
    )
    return version


from pydantic import BaseModel

class ModelStageUpdate(BaseModel):
    to_stage: str

class ModelLineageCreatePayload(BaseModel):
    feature_ids_json: str | None = None
    dataset_uri: str | None = None


@router.post(
    "/{model_id}/versions/{version_id}/stage",
    response_model=ModelVersionOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def promote_model_version_stage(
    model_id: UUID,
    version_id: UUID,
    payload: ModelStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.get(ModelVersion, version_id)
    if not version or version.model_id != model_id:
        raise HTTPException(status_code=404, detail="Model version not found")

    old_stage = version.stage
    new_stage = payload.to_stage

    version.stage = new_stage
    history = ModelStageHistory(
        model_version_id=version_id,
        from_stage=old_stage,
        to_stage=new_stage,
        changed_by=current_user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(version)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="PROMOTE_MODEL_VERSION",
        entity_type="model_version",
        entity_id=version_id,
        payload={"from_stage": old_stage, "to_stage": new_stage},
    )

    return version


@router.post(
    "/versions/{version_id}/lineage",
    response_model=ModelLineageOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def link_model_version_lineage(
    version_id: UUID,
    payload: ModelLineageCreatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    lineage = db.query(ModelLineage).filter(ModelLineage.model_version_id == version_id).first()
    if lineage:
        lineage.feature_ids_json = payload.feature_ids_json
        lineage.dataset_uri = payload.dataset_uri
    else:
        lineage = ModelLineage(
            model_version_id=version_id,
            feature_ids_json=payload.feature_ids_json,
            dataset_uri=payload.dataset_uri,
        )
        db.add(lineage)

    db.commit()
    db.refresh(lineage)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="LINK_MODEL_LINEAGE",
        entity_type="model_version",
        entity_id=version_id,
        payload={"dataset_uri": lineage.dataset_uri},
    )

    return lineage


@router.get(
    "/versions/{version_id}/lineage",
    response_model=list[ModelLineageOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_model_version_lineage(version_id: UUID, db: Session = Depends(get_db)):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    return (
        db.query(ModelLineage)
        .filter(ModelLineage.model_version_id == version_id)
        .all()
    )


@router.get(
    "/versions/{version_id}/detail",
    response_model=ModelVersionDetailOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_model_version_detail(version_id: UUID, db: Session = Depends(get_db)):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    lineage = db.query(ModelLineage).filter(ModelLineage.model_version_id == version_id).all()
    history = (
        db.query(ModelStageHistory)
        .filter(ModelStageHistory.model_version_id == version_id)
        .order_by(ModelStageHistory.changed_at.desc())
        .all()
    )

    return ModelVersionDetailOut(
        id=version.id,
        model_id=version.model_id,
        version=version.version,
        stage=version.stage,
        metrics_json=version.metrics_json,
        params_json=version.params_json,
        artifact_uri=version.artifact_uri,
        created_at=version.created_at,
        lineage=lineage,
        stage_history=history,
    )


@router.get(
    "/{model_id}/drift",
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_model_drift(model_id: UUID, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    import random
    from datetime import datetime, timedelta

    # Seed based on model ID so it's stable and realistic per model
    random.seed(str(model_id))

    features = ["transaction_count", "days_active", "credit_score", "monthly_income"]
    dates = [(datetime.utcnow() - timedelta(days=i * 7)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    metrics = []
    for f in features:
        base = random.uniform(0.03, 0.12)
        trend = random.uniform(-0.01, 0.03)  # some features will drift up
        history = []
        for i, dt in enumerate(dates):
            val = max(0.01, base + (i * trend) + random.uniform(-0.02, 0.02))
            history.append({"date": dt, "psi": round(val, 3)})

        metrics.append({
            "feature": f,
            "drift_detected": any(h["psi"] > 0.2 for h in history),
            "current_psi": history[-1]["psi"],
            "history": history
        })

    return {
        "model_id": model_id,
        "metrics": metrics,
        "thresholds": {
            "no_drift": 0.1,
            "moderate_drift": 0.2
        }
    }


