from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core import roles
from app.db.models.feature_store import FeatureDefinition, FeatureMaterialization, FeatureValueOnline
from app.db.models.model_registry import Model, ModelStageHistory, ModelVersion
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary, DashboardStat, MaterializationItem, PromotionItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))],
)
def summary(db: Session = Depends(get_db)):
    feature_count = db.query(func.count(FeatureDefinition.id)).scalar() or 0
    model_count = db.query(func.count(Model.id)).scalar() or 0

    last_materialization = (
        db.query(FeatureMaterialization)
        .order_by(FeatureMaterialization.started_at.desc())
        .first()
    )
    if last_materialization and last_materialization.started_at:
        st = last_materialization.started_at
        if st.tzinfo is not None:
            now = datetime.now(st.tzinfo)
        else:
            now = datetime.utcnow()
        delta = now - st
        mins = int(delta.total_seconds() / 60)
        last_materialization_value = f"{mins} min ago" if mins > 0 else "Just now"
    else:
        last_materialization_value = "Never"

    # Serving freshness is the latest event time versus the feature's declared cadence.
    active = db.query(FeatureDefinition).filter(FeatureDefinition.status == "active").all()
    latest_events = dict(db.query(FeatureValueOnline.feature_id, func.max(FeatureValueOnline.event_time))
                         .group_by(FeatureValueOnline.feature_id).all())
    seconds = {"streaming": 300, "hourly": 3600, "daily": 86400, "weekly": 604800}
    known = [feature for feature in active if feature.refresh_interval in seconds]
    fresh = 0
    now = datetime.now(timezone.utc)
    for feature in known:
        event_time = latest_events.get(feature.id)
        if event_time:
            event_time = event_time.replace(tzinfo=timezone.utc) if event_time.tzinfo is None else event_time
            age = (now - event_time).total_seconds()
            fresh += 0 <= age <= seconds[feature.refresh_interval]
    freshness_pct = f"{round(100 * fresh / len(known))}%" if known else "N/A"
    freshness_note = f"{fresh}/{len(known)} active features within event-age policy; {len(active) - len(known)} unknown cadence"

    stats = [
        DashboardStat(label="Active Features", value=str(len(active)), note="Active definitions"),
        DashboardStat(label="Models in Registry", value=str(model_count), note="All lifecycle stages"),
        DashboardStat(
            label="Last Materialization",
            value=last_materialization_value,
            note="Latest execution",
        ),
        DashboardStat(label="Data Freshness", value=freshness_pct, note=freshness_note),
    ]

    recent_materializations = []
    recent_runs = (
        db.query(FeatureMaterialization, FeatureDefinition.name)
        .outerjoin(FeatureDefinition, FeatureDefinition.id == FeatureMaterialization.feature_id)
        .order_by(FeatureMaterialization.started_at.desc())
        .limit(6)
        .all()
    )
    for run, feat_name in recent_runs:
        display_name = feat_name or str(run.feature_id)[:8]
        recent_materializations.append(
            MaterializationItem(
                name=display_name,
                status=run.status,
                time=run.started_at.isoformat() if run.started_at else "unknown",
            )
        )

    recent_promotions = []
    promotions = (
        db.query(ModelStageHistory, ModelVersion.version, Model.name)
        .outerjoin(ModelVersion, ModelVersion.id == ModelStageHistory.model_version_id)
        .outerjoin(Model, Model.id == ModelVersion.model_id)
        .order_by(ModelStageHistory.changed_at.desc())
        .limit(6)
        .all()
    )
    for promo, ver_str, mod_name in promotions:
        model_display = f"{mod_name or 'Model'} v{ver_str}" if ver_str else str(promo.model_version_id)[:8]
        recent_promotions.append(
            PromotionItem(
                model=model_display,
                stage=promo.to_stage,
                time=promo.changed_at.isoformat(),
            )
        )

    return DashboardSummary(
        stats=stats,
        recent_materializations=recent_materializations,
        recent_promotions=recent_promotions,
    )
