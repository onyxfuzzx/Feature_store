import json
import time
from typing import Literal
from uuid import UUID

from app.api.deps import get_current_user, require_roles
from app.api.pagination import page, page_limit, page_offset
from app.core import roles
from app.db.models.core import User
from app.db.models.model_registry import (
    InferenceObservation,
    Model,
    ModelLineage,
    ModelStageHistory,
    ModelVersion,
)
from app.db.session import get_db
from app.schemas.drift import BaselineCreate, DriftRunCreate
from app.schemas.feature_store import LineageGraphOut
from app.schemas.model_registry import (
    ModelCreate,
    ModelHydrateRequest,
    ModelHydrateResponse,
    ModelLineageOut,
    ModelOut,
    ModelPredictRequest,
    ModelPredictResponse,
    ModelVersionCreate,
    ModelVersionDetailOut,
    ModelVersionOut,
)
from app.services import drift
from app.services.artifacts import artifact_path, store_artifact
from app.services.audit import log_audit
from app.services.drift import calculate_psi as calculate_psi
from app.services.feature_refs import resolve_feature, resolve_features
from app.services.model_runtime import hydrate, load_model, score
from app.services.registry import transition
from app.services.validation import coerce_value
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "",
    response_model=list[ModelOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_models(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    return page(
        db.query(Model).order_by(Model.created_at.desc(), Model.id.desc()), response, limit, offset
    )


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
    db.flush()
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_MODEL",
        entity_type="model",
        entity_id=model.id,
        payload={"name": model.name},
        commit=False,
    )
    db.commit()
    db.refresh(model)
    return model


@router.get(
    "/{model_id}",
    response_model=ModelOut,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_model(model_id: UUID, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.get(
    "/{model_id}/versions",
    response_model=list[ModelVersionOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_model_versions(
    model_id: UUID,
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return page(
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id)
        .order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc()),
        response,
        limit,
        offset,
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
    model = db.query(Model).filter_by(id=model_id).with_for_update().first()
    if not model:
        raise HTTPException(404, "Model not found")
    if db.query(ModelVersion).filter_by(model_id=model_id, version=payload.version).first():
        raise HTTPException(409, "Model version already exists")
    version = ModelVersion(
        model_id=model_id,
        version=payload.version,
        stage="Staging",
        metrics_json=payload.metrics_json,
        params_json=payload.params_json,
    )
    db.add(version)
    db.flush()
    transition(db, version, payload.stage, current_user.id)
    log_audit(
        db,
        current_user.id,
        "CREATE_MODEL_VERSION",
        "model_version",
        version.id,
        {"model_id": str(model_id), "version": version.version, "stage": version.stage},
        commit=False,
    )
    db.commit()
    db.refresh(version)
    return version


class ModelStageUpdate(BaseModel):
    to_stage: Literal["Staging", "Production", "Archived"]


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
    model = db.query(Model).filter_by(id=model_id).with_for_update().first()
    version = db.get(ModelVersion, version_id)
    if not model or not version or version.model_id != model_id:
        raise HTTPException(404, "Model version not found")
    transition(db, version, payload.to_stage, current_user.id)
    db.commit()
    db.refresh(version)
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
    version = db.query(ModelVersion).filter_by(id=version_id).with_for_update().first()
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    try:
        references = json.loads(payload.feature_ids_json or "[]")
    except ValueError as exc:
        raise HTTPException(422, "feature_ids_json must be a JSON list") from exc
    if (
        not isinstance(references, list)
        or len(references) > 100
        or not all(isinstance(item, str) for item in references)
    ):
        raise HTTPException(422, "Model lineage requires a list of at most 100 feature references")
    model = db.get(Model, version.model_id)
    features, _ = resolve_features(db, references, model.environment)
    # Do not let the displayed/training lineage omit features the artifact actually serves.
    if version.artifact_uri and version.artifact_uri.startswith("artifact://"):
        from app.services.model_runtime import LinearArtifact

        try:
            manifest = LinearArtifact.model_validate_json(
                artifact_path(version.artifact_uri, version.model_id, version.id).read_bytes()
            )
        except (ValueError, OSError):
            manifest = None
        required = (
            {item.feature_id for item in manifest.inputs if item.feature_id} if manifest else set()
        )
        if not required.issubset({feature.id for feature in features}):
            raise HTTPException(422, "Cannot unlink a feature required by the registered artifact")
    payload.feature_ids_json = json.dumps([str(feature.id) for feature in features])

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

    db.flush()

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="LINK_MODEL_LINEAGE",
        entity_type="model_version",
        entity_id=version_id,
        payload={"dataset_uri": lineage.dataset_uri},
        commit=False,
    )

    db.commit()
    db.refresh(lineage)
    return lineage


@router.get(
    "/versions/{version_id}/lineage",
    response_model=list[ModelLineageOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_model_version_lineage(version_id: UUID, db: Session = Depends(get_db)):
    version = db.get(ModelVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    return db.query(ModelLineage).filter(ModelLineage.model_version_id == version_id).all()


@router.get(
    "/versions/{version_id}/detail",
    response_model=ModelVersionDetailOut,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
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
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_model_drift(model_id: UUID, version: str | None = None, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    query = db.query(ModelVersion).filter_by(model_id=model_id)
    if version:
        selected = query.filter_by(version=version).first()
        if not selected:
            raise HTTPException(404, "Model version not found")
    else:
        selected = (
            query.filter_by(stage="Production").first()
            or query.order_by(ModelVersion.created_at.desc()).first()
        )
    return drift.summary(db, model, selected)


@router.post(
    "/{model_id}/versions/{version_id}/drift-baseline",
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_drift_baseline(
    model_id: UUID,
    version_id: UUID,
    payload: BaselineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = db.get(ModelVersion, version_id)
    if not version or version.model_id != model_id:
        raise HTTPException(404, "Model version not found")
    baseline = drift.capture_baseline(db, version, payload)
    log_audit(
        db,
        current_user.id,
        "CAPTURE_DRIFT_BASELINE",
        "model_version",
        version.id,
        {"baseline_id": str(baseline.id)},
        commit=False,
    )
    db.commit()
    return {
        "id": str(baseline.id),
        "version_id": str(version.id),
        "distributions": baseline.distributions,
    }


@router.post(
    "/{model_id}/drift/runs",
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def run_model_drift(model_id: UUID, payload: DriftRunCreate, db: Session = Depends(get_db)):
    version = serving_version(db, model_id, payload.version)
    run = drift.record_run(db, version, payload)
    db.commit()
    return {"id": str(run.id), "status": run.status, "metrics": run.result_json["metrics"]}


@router.post(
    "/{model_id}/versions/{version_id}/artifact",
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def upload_model_artifact(
    model_id: UUID,
    version_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload model binary / weights artifact (.pkl, .onnx, .tar.gz, etc.)
    """
    version = db.query(ModelVersion).filter_by(id=version_id).with_for_update().first()
    if not version or version.model_id != model_id:
        raise HTTPException(status_code=404, detail="Model version not found")

    uri, path, size = store_artifact(file, model_id, version_id)
    try:
        version.artifact_uri = uri
        from app.services.model_runtime import LinearArtifact

        try:
            manifest = LinearArtifact.model_validate_json(path.read_bytes())
        except ValueError:
            manifest = None  # opaque artifact storage remains supported
        if manifest:
            identifiers = [str(item.feature_id) for item in manifest.inputs if item.feature_id]
            model = db.get(Model, model_id)
            for identifier in identifiers:
                resolve_feature(db, identifier, model.environment)
            lineage = db.query(ModelLineage).filter_by(model_version_id=version.id).first()
            if not lineage:
                lineage = ModelLineage(model_version_id=version.id)
                db.add(lineage)
            lineage.feature_ids_json = json.dumps(identifiers)
        log_audit(
            db,
            current_user.id,
            "UPLOAD_MODEL_ARTIFACT",
            "model_version",
            str(version.id),
            {"filename": file.filename, "size_bytes": size},
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return {"status": "success", "filename": file.filename, "artifact_uri": uri, "size_bytes": size}


@router.get(
    "/{model_id}/versions/{version_id}/artifact",
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def download_model_artifact(
    model_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Download stored model binary artifact.
    """
    version = db.get(ModelVersion, version_id)
    if not version or version.model_id != model_id:
        raise HTTPException(status_code=404, detail="Model version not found")

    path = artifact_path(version.artifact_uri, model_id, version_id)
    if not path.is_file():
        raise HTTPException(404, "Artifact file not found on storage")
    return FileResponse(
        path=path, filename=f"model-{version.version}.bin", media_type="application/octet-stream"
    )


@router.get(
    "/{model_id}/lineage-graph",
    response_model=LineageGraphOut,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_model_lineage_graph(
    model_id: UUID,
    db: Session = Depends(get_db),
):
    from app.services.lineage import graph

    return graph(db, model_id=model_id)


def serving_version(db, model_id, requested_version):
    if not db.get(Model, model_id):
        raise HTTPException(404, "Model not found")
    query = db.query(ModelVersion).filter(ModelVersion.model_id == model_id)
    if requested_version:
        version = query.filter(ModelVersion.version == requested_version).first()
    else:
        version = (
            query.filter(ModelVersion.stage == "Production")
            .order_by(ModelVersion.created_at.desc())
            .first()
        )
    if not version:
        raise HTTPException(
            404, "Requested version unavailable; specify a version or promote one to Production"
        )
    return version


@router.post(
    "/{model_id}/hydrate",
    response_model=ModelHydrateResponse,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def hydrate_model_features(
    model_id: UUID, payload: ModelHydrateRequest, db: Session = Depends(get_db)
):
    start = time.perf_counter()
    version = serving_version(db, model_id, payload.version)
    artifact = load_model(version, db)
    records = hydrate(artifact, payload.entity_keys, db)
    return ModelHydrateResponse(
        model_id=model_id,
        version=version.version,
        features=[item.name for item in artifact.inputs],
        hydrated_records=records,
        latency_ms=round((time.perf_counter() - start) * 1000, 3),
    )


@router.post(
    "/{model_id}/predict",
    response_model=ModelPredictResponse,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def predict_with_model(model_id: UUID, payload: ModelPredictRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    version = serving_version(db, model_id, payload.version)
    artifact = load_model(version, db)
    record = hydrate(artifact, [payload.entity_key], db)[0]
    used, prediction = score(artifact, record, payload.runtime_features)
    prediction["model_version"] = version.version
    observed = {
        str(item.feature_id): float(coerce_value(used[item.name], item.dtype))
        for item in artifact.inputs
        if item.feature_id
    }
    db.add(
        InferenceObservation(
            model_version_id=version.id, entity_key=payload.entity_key, values_json=observed
        )
    )
    db.commit()
    return ModelPredictResponse(
        model_id=model_id,
        version=version.version,
        entity_key=payload.entity_key,
        features_used=used,
        prediction=prediction,
        latency_ms=round((time.perf_counter() - start) * 1000, 3),
    )
