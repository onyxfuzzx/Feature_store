from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core import roles
from app.db.models.feature_store import FeatureDefinition, FeatureMaterialization
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
        delta = datetime.utcnow() - last_materialization.started_at
        mins = int(delta.total_seconds() / 60)
        last_materialization_value = f"{mins} min ago" if mins > 0 else "Just now"
    else:
        last_materialization_value = "Never"

    # Compute actual freshness SLA: ratio of successful runs in the last 20 runs
    recent_20_runs = db.query(FeatureMaterialization).order_by(FeatureMaterialization.started_at.desc()).limit(20).all()
    if recent_20_runs:
        success_count = sum(1 for r in recent_20_runs if r.status == "success")
        freshness_pct = f"{int((success_count / len(recent_20_runs)) * 100)}%"
        freshness_note = f"{success_count}/{len(recent_20_runs)} runs passed"
    else:
        freshness_pct = "100%"
        freshness_note = "Standby"

    stats = [
        DashboardStat(label="Active Features", value=str(feature_count), note="Registered features"),
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
