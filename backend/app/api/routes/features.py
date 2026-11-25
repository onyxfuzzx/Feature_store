import time
from datetime import UTC, datetime
from uuid import UUID

from app.api.deps import get_current_user, require_roles
from app.api.pagination import page, page_limit, page_offset
from app.core import roles
from app.db.models.core import User
from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureGroup,
    FeatureLineage,
    FeatureMaterialization,
    FeatureValueOffline,
    FeatureValueOnline,
)
from app.db.session import get_db
from app.schemas.feature_store import (
    AsOfJoinRequest,
    AsOfJoinResponse,
    BatchOnlineFeaturesRequest,
    BatchOnlineFeaturesResponse,
    FeatureDefinitionCreate,
    FeatureDefinitionOut,
    FeatureDefinitionUpdate,
    FeatureGroupCreate,
    FeatureGroupOut,
    FeatureLineageCreate,
    FeatureLineageOut,
    FeatureMaterializationOut,
    LineageGraphOut,
    QueryDryRunRequest,
    QueryDryRunResponse,
    StreamIngestRequest,
    StreamIngestResponse,
)
from app.services.audit import log_audit
from app.services.feature_refs import resolve_feature, resolve_features
from app.services.historical import historical_rows
from app.services.materialization import materialize_feature, write_offline_values
from app.services.online_store import get_online_store
from app.services.source_queries import execute_source_query
from app.services.validation import parse_rules, validate_value
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/features", tags=["features"])


@router.get(
    "/groups",
    response_model=list[FeatureGroupOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_feature_groups(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    return page(
        db.query(FeatureGroup).order_by(FeatureGroup.created_at.desc(), FeatureGroup.id.desc()),
        response,
        limit,
        offset,
    )


@router.post(
    "/groups",
    response_model=FeatureGroupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_feature_group(
    payload: FeatureGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = FeatureGroup(
        name=payload.name,
        description=payload.description,
        owner_id=payload.owner_id,
        tags_json=payload.tags_json,
        environment=payload.environment,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_FEATURE_GROUP",
        entity_type="feature_group",
        entity_id=group.id,
        payload={"name": group.name, "description": group.description},
    )
    return group


@router.get(
    "",
    response_model=list[FeatureDefinitionOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_features(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    return page(
        db.query(FeatureDefinition).order_by(
            FeatureDefinition.created_at.desc(), FeatureDefinition.id.desc()
        ),
        response,
        limit,
        offset,
    )


@router.post(
    "",
    response_model=FeatureDefinitionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_feature(
    payload: FeatureDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(FeatureGroup, payload.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Feature group not found")

    feature = FeatureDefinition(
        group_id=payload.group_id,
        name=payload.name,
        dtype=payload.dtype,
        description=payload.description,
        source_sql=payload.source_sql,
        refresh_interval=payload.refresh_interval,
        status=payload.status,
        validation_rules_json=payload.validation_rules_json,
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_FEATURE",
        entity_type="feature_definition",
        entity_id=feature.id,
        payload={"name": feature.name, "dtype": feature.dtype, "status": feature.status},
    )
    return feature


@router.get(
    "/{feature_id}",
    response_model=FeatureDefinitionOut,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_feature(feature_id: UUID, db: Session = Depends(get_db)):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.post(
    "/{feature_id}/materialize",
    response_model=FeatureMaterializationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def materialize(
    feature_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = materialize_feature(db, feature_id)
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="MATERIALIZE_FEATURE",
        entity_type="feature_definition",
        entity_id=feature_id,
        payload={
            "materialization_id": str(run.id),
            "status": run.status,
            "row_count": run.row_count,
        },
    )
    return run


@router.get(
    "/{feature_id}/materializations",
    response_model=list[FeatureMaterializationOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_materializations(
    feature_id: UUID,
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    return page(
        db.query(FeatureMaterialization)
        .filter(FeatureMaterialization.feature_id == feature_id)
        .order_by(FeatureMaterialization.started_at.desc(), FeatureMaterialization.id.desc()),
        response,
        limit,
        offset,
    )


@router.get(
    "/{feature_id}/values",
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_feature_values(feature_id: UUID, db: Session = Depends(get_db)):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    online_vals = (
        db.query(FeatureValueOnline)
        .filter(FeatureValueOnline.feature_id == feature_id)
        .limit(100)
        .all()
    )
    offline_vals = (
        db.query(FeatureValueOffline)
        .filter(FeatureValueOffline.feature_id == feature_id)
        .order_by(FeatureValueOffline.event_time.desc())
        .limit(100)
        .all()
    )

    return {
        "online": [
            {
                "entity_key": v.entity_key,
                "feature_id": v.feature_id,
                "value": v.value,
                "event_time": v.event_time.isoformat() if v.event_time else None,
                "updated_at": v.updated_at.isoformat(),
            }
            for v in online_vals
        ],
        "offline": [
            {
                "entity_key": v.entity_key,
                "feature_id": v.feature_id,
                "value": v.value,
                "event_time": v.event_time.isoformat(),
                "updated_at": v.updated_at.isoformat(),
            }
            for v in offline_vals
        ],
    }


@router.post(
    "/{feature_id}/lineage",
    response_model=FeatureLineageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def create_feature_lineage(
    feature_id: UUID,
    payload: FeatureLineageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    lineage = FeatureLineage(
        feature_id=feature_id,
        source_table=payload.source_table,
        source_columns_json=payload.source_columns_json,
    )
    db.add(lineage)
    db.commit()
    db.refresh(lineage)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="ADD_FEATURE_LINEAGE",
        entity_type="feature_definition",
        entity_id=feature_id,
        payload={"source_table": lineage.source_table},
    )

    return lineage


@router.get(
    "/{feature_id}/lineage",
    response_model=list[FeatureLineageOut],
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def list_feature_lineage(feature_id: UUID, db: Session = Depends(get_db)):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    return (
        db.query(FeatureLineage)
        .filter(FeatureLineage.feature_id == feature_id)
        .order_by(FeatureLineage.created_at.desc())
        .all()
    )


@router.put(
    "/{feature_id}",
    response_model=FeatureDefinitionOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def update_feature(
    feature_id: UUID,
    payload: FeatureDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    if payload.description is not None:
        feature.description = payload.description
    if payload.status is not None:
        feature.status = payload.status
    if payload.refresh_interval is not None:
        feature.refresh_interval = payload.refresh_interval
    if payload.validation_rules_json is not None:
        feature.validation_rules_json = payload.validation_rules_json

    db.commit()
    db.refresh(feature)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="UPDATE_FEATURE",
        entity_type="feature_definition",
        entity_id=feature.id,
        payload={"name": feature.name, "status": feature.status},
    )

    return feature


@router.post(
    "/online/batch",
    response_model=BatchOnlineFeaturesResponse,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_batch_online_features(
    payload: BatchOnlineFeaturesRequest,
    db: Session = Depends(get_db),
):
    start_time = time.perf_counter()

    resolved_features, feature_id_map = resolve_features(db, payload.features, payload.environment)
    store = get_online_store()
    values_result = store.get_online_features(payload.entity_keys, feature_id_map, db)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 3)

    return BatchOnlineFeaturesResponse(
        entity_keys=payload.entity_keys,
        features=list(feature_id_map.values()),
        values=values_result,
        read_latency_ms=latency_ms,
    )


@router.post(
    "/offline/as-of-join",
    response_model=AsOfJoinResponse,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def compute_as_of_join(
    payload: AsOfJoinRequest,
    db: Session = Depends(get_db),
):
    """
    Point-in-time correct join (As-Of join) for training dataset generation.
    For each (entity_key, event_time) observation, gets the latest feature value
    recorded AT or BEFORE the observation event_time (preventing target leakage).
    """
    start_time = time.perf_counter()

    resolved_features, feature_id_map = resolve_features(db, payload.features, payload.environment)

    joined_rows = historical_rows(db, payload.observations, feature_id_map)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    return AsOfJoinResponse(
        joined_rows=joined_rows,
        row_count=len(joined_rows),
        computation_time_ms=elapsed_ms,
    )


@router.post(
    "/stream-ingest",
    response_model=StreamIngestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER))],
)
def stream_ingest(
    payload: StreamIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Push streaming events into the online store in real time, with optional offline history write.
    """
    now = datetime.now(UTC)
    records = []
    resolved = {}
    rules = {}
    for record in payload.records:
        reference = str(record.feature_id or record.feature_name)
        if reference not in resolved:
            resolved[reference] = resolve_feature(db, reference, payload.environment)
        feat = resolved[reference]
        if feat.id not in rules:
            rules[feat.id] = parse_rules(feat.validation_rules_json)
        errors = validate_value(record.value, rules[feat.id], feat.dtype)
        if errors:
            raise HTTPException(
                422, f"Validation rejected {record.entity_key}: {', '.join(errors)}"
            )
        records.append(
            {
                "entity_key": record.entity_key,
                "feature_id": feat.id,
                "value": record.value,
                "event_time": record.event_time or now,
                "updated_at": now,
            }
        )
    try:
        if payload.persist_offline:
            write_offline_values(db, records)
        online_updated_count = get_online_store().write_online_features(records, db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return StreamIngestResponse(
        ingested_count=len(records),
        online_updated_count=online_updated_count,
        success=True,
        timestamp=now,
    )


@router.post(
    "/dry-run",
    response_model=QueryDryRunResponse,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST))],
)
def dry_run_query(
    payload: QueryDryRunRequest,
    db: Session = Depends(get_db),
):
    """
    Safely executes an exploratory SQL query with a row limit to preview feature transformations.
    Restricts destructive DDL/DML keywords.
    """
    start = time.perf_counter()
    try:
        columns, raw_rows = execute_source_query(payload.query, payload.limit)
        rows = [
            {col: (str(value) if value is not None else None) for col, value in row.items()}
            for row in raw_rows
        ]
        return QueryDryRunResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )
    except Exception as exc:
        return QueryDryRunResponse(
            is_valid=False,
            error=str(exc),
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )


@router.get(
    "/{feature_id}/lineage-graph",
    response_model=LineageGraphOut,
    dependencies=[
        Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))
    ],
)
def get_feature_lineage_graph(
    feature_id: UUID,
    db: Session = Depends(get_db),
):
    from app.services.lineage import graph

    return graph(db, feature_id=feature_id)
