import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_roles, get_current_user
from app.core import roles
from app.db.models.core import User
from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureGroup,
    FeatureMaterialization,
    FeatureLineage,
    FeatureValueOnline,
    FeatureValueOffline,
)
from app.db.models.model_registry import Model, ModelVersion, ModelLineage
from app.db.session import get_db
from app.schemas.feature_store import (
    FeatureDefinitionCreate,
    FeatureDefinitionOut,
    FeatureDefinitionUpdate,
    FeatureGroupCreate,
    FeatureGroupOut,
    FeatureMaterializationOut,
    FeatureLineageCreate,
    FeatureLineageOut,
    FeatureValueOut,
    BatchOnlineFeaturesRequest,
    BatchOnlineFeaturesResponse,
    AsOfJoinRequest,
    AsOfJoinResponse,
    StreamIngestRequest,
    StreamIngestResponse,
    QueryDryRunRequest,
    QueryDryRunResponse,
    LineageGraphOut,
    LineageNode,
    LineageEdge,
)
from app.services.materialization import materialize_feature
from app.services.audit import log_audit
from app.services.online_store import get_online_store


router = APIRouter(prefix="/features", tags=["features"])


@router.get(
    "/groups",
    response_model=list[FeatureGroupOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def list_feature_groups(db: Session = Depends(get_db)):
    return db.query(FeatureGroup).order_by(FeatureGroup.created_at.desc()).all()


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
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def list_features(db: Session = Depends(get_db)):
    return db.query(FeatureDefinition).order_by(FeatureDefinition.created_at.desc()).all()


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
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
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
        payload={"materialization_id": str(run.id), "status": run.status, "row_count": run.row_count},
    )
    return run


@router.get(
    "/{feature_id}/materializations",
    response_model=list[FeatureMaterializationOut],
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def list_materializations(feature_id: UUID, db: Session = Depends(get_db)):
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    return (
        db.query(FeatureMaterialization)
        .filter(FeatureMaterialization.feature_id == feature_id)
        .order_by(FeatureMaterialization.started_at.desc())
        .all()
    )


@router.get(
    "/{feature_id}/values",
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
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
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
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
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_batch_online_features(
    payload: BatchOnlineFeaturesRequest,
    db: Session = Depends(get_db),
):
    start_time = time.perf_counter()

    resolved_features: dict[str, FeatureDefinition] = {}
    for feat_ref in payload.features:
        feat = None
        try:
            feat = db.get(FeatureDefinition, UUID(feat_ref))
        except (ValueError, AttributeError):
            pass

        if not feat:
            if ":" in feat_ref:
                grp_name, f_name = feat_ref.split(":", 1)
                feat = (
                    db.query(FeatureDefinition)
                    .join(FeatureGroup, FeatureGroup.id == FeatureDefinition.group_id)
                    .filter(FeatureGroup.name == grp_name, FeatureDefinition.name == f_name)
                    .first()
                )
            else:
                feat = db.query(FeatureDefinition).filter(FeatureDefinition.name == feat_ref).first()

        if feat:
            resolved_features[feat_ref] = feat

    feature_id_map = {feat.id: feat.name for feat in resolved_features.values()}
    store = get_online_store()
    raw_results = store.get_online_features(payload.entity_keys, feature_id_map, db)

    # Align with payload requested aliases/references
    values_result: dict[str, dict[str, str | None]] = {}
    for ek in payload.entity_keys:
        values_result[ek] = {}
        for feat_ref, feat in resolved_features.items():
            values_result[ek][feat.name] = raw_results.get(ek, {}).get(feat.name, None)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 3)

    return BatchOnlineFeaturesResponse(
        entity_keys=payload.entity_keys,
        features=[f.name for f in resolved_features.values()],
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

    resolved_features = []
    for feat_ref in payload.features:
        feat = None
        try:
            feat = db.get(FeatureDefinition, UUID(feat_ref))
        except (ValueError, AttributeError):
            pass
        if not feat:
            feat = db.query(FeatureDefinition).filter(FeatureDefinition.name == feat_ref).first()
        if feat:
            resolved_features.append(feat)

    joined_rows = []
    for obs in payload.observations:
        row_dict: dict[str, str | None] = {
            "entity_key": obs.entity_key,
            "event_time": obs.event_time.isoformat(),
        }
        for feat in resolved_features:
            latest_val = (
                db.query(FeatureValueOffline.value)
                .filter(
                    FeatureValueOffline.entity_key == obs.entity_key,
                    FeatureValueOffline.feature_id == feat.id,
                    FeatureValueOffline.event_time <= obs.event_time,
                )
                .order_by(FeatureValueOffline.event_time.desc())
                .first()
            )
            row_dict[feat.name] = latest_val[0] if latest_val else None

        joined_rows.append(row_dict)

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
    now = datetime.utcnow()
    ingested = 0

    for record in payload.records:
        feat = None
        if record.feature_id:
            feat = db.get(FeatureDefinition, record.feature_id)
        elif record.feature_name:
            feat = db.query(FeatureDefinition).filter(FeatureDefinition.name == record.feature_name).first()

        if not feat:
            continue

        evt_time = record.event_time or now

        online_entry = (
            db.query(FeatureValueOnline)
            .filter(
                FeatureValueOnline.entity_key == record.entity_key,
                FeatureValueOnline.feature_id == feat.id,
            )
            .first()
        )
        if online_entry:
            online_entry.value = record.value
            online_entry.event_time = evt_time
            online_entry.updated_at = now
        else:
            online_entry = FeatureValueOnline(
                entity_key=record.entity_key,
                feature_id=feat.id,
                value=record.value,
                event_time=evt_time,
                updated_at=now,
            )
            db.add(online_entry)

        if payload.persist_offline:
            offline_entry = FeatureValueOffline(
                entity_key=record.entity_key,
                feature_id=feat.id,
                value=record.value,
                event_time=evt_time,
                updated_at=now,
            )
            db.add(offline_entry)

        ingested += 1

    db.commit()

    # Mirror to configured online store cache
    try:
        online_store = get_online_store()
        cache_records = [
            {"entity_key": r.entity_key, "feature_id": r.feature_id, "value": r.value, "event_time": r.event_time}
            for r in payload.records if r.feature_id
        ]
        if cache_records:
            online_store.write_online_features(cache_records, db)
    except Exception:
        pass

    return StreamIngestResponse(
        ingested_count=ingested,
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
    cleaned = payload.query.strip().rstrip(";")
    upper_q = cleaned.upper()
    disallowed = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE ", "GRANT ", "REVOKE "]
    if any(kw in upper_q for kw in disallowed):
        return QueryDryRunResponse(
            is_valid=False,
            error="Only read-only SELECT queries are allowed for feature transformations.",
        )

    limited_query = f"SELECT * FROM ({cleaned}) AS subq LIMIT {min(payload.limit, 50)}"
    start = time.perf_counter()
    try:
        result = db.execute(text(limited_query))
        columns = list(result.keys())
        raw_rows = result.fetchall()
        rows = [
            {col: (str(val) if val is not None else None) for col, val in zip(columns, row)}
            for row in raw_rows
        ]
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return QueryDryRunResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            is_valid=True,
        )
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return QueryDryRunResponse(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=elapsed_ms,
            is_valid=False,
            error=str(e),
        )


@router.get(
    "/{feature_id}/lineage-graph",
    response_model=LineageGraphOut,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def get_feature_lineage_graph(
    feature_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Returns the visual DAG dependency graph for a feature:
    Upstream tables -> Feature Group -> Feature -> Downstream Models -> Serving Endpoints.
    """
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    group = db.get(FeatureGroup, feature.group_id)
    nodes: list[LineageNode] = []
    edges: list[LineageEdge] = []

    # 1. Feature Node
    feat_node_id = f"feat:{feature.id}"
    nodes.append(LineageNode(
        id=feat_node_id,
        label=feature.name,
        type="feature",
        metadata={"dtype": feature.dtype, "status": feature.status, "interval": feature.refresh_interval}
    ))

    # 2. Group Node
    if group:
        grp_node_id = f"grp:{group.id}"
        nodes.append(LineageNode(
            id=grp_node_id,
            label=group.name,
            type="feature_group",
            metadata={"environment": group.environment}
        ))
        edges.append(LineageEdge(source=grp_node_id, target=feat_node_id, label="contains"))

    # 3. Source Tables
    lineages = db.query(FeatureLineage).filter(FeatureLineage.feature_id == feature_id).all()
    source_tables = {l.source_table for l in lineages} if lineages else set()
    if not source_tables:
        source_tables.add("feature_store.raw_events")

    for tbl in source_tables:
        src_id = f"source:{tbl}"
        nodes.append(LineageNode(
            id=src_id,
            label=tbl,
            type="source_table",
            metadata={"storage": "PostgreSQL"}
        ))
        edges.append(LineageEdge(source=src_id, target=feat_node_id, label="transforms"))

    # 4. Downstream Models
    all_ml = db.query(ModelLineage).all()
    consumed_version_ids = []
    for ml in all_ml:
        if ml.feature_ids_json and (str(feature_id) in ml.feature_ids_json or feature.name in ml.feature_ids_json):
            consumed_version_ids.append(ml.model_version_id)

    if consumed_version_ids:
        versions = db.query(ModelVersion).filter(ModelVersion.id.in_(consumed_version_ids)).all()
        for v in versions:
            m = db.get(Model, v.model_id)
            model_name = m.name if m else "ML Model"
            m_node_id = f"model:{v.id}"
            nodes.append(LineageNode(
                id=m_node_id,
                label=f"{model_name} (v{v.version})",
                type="model",
                metadata={"stage": v.stage}
            ))
            edges.append(LineageEdge(source=feat_node_id, target=m_node_id, label="feeds"))

            if v.stage == "Production":
                ep_node_id = f"endpoint:{v.id}"
                nodes.append(LineageNode(
                    id=ep_node_id,
                    label=f"POST /predict ({model_name})",
                    type="endpoint",
                    metadata={"target": "Live Inference"}
                ))
                edges.append(LineageEdge(source=m_node_id, target=ep_node_id, label="serves"))

    return LineageGraphOut(nodes=nodes, edges=edges)



