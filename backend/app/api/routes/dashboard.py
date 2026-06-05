from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core import roles
from app.db.models.feature_store import FeatureDefinition, FeatureMaterialization
from app.db.models.model_registry import Model, ModelStageHistory
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
        last_materialization_value = f"{int(delta.total_seconds() / 60)} min"
    else:
        last_materialization_value = "N/A"

    stats = [
        DashboardStat(label="Active Features", value=str(feature_count), note="All definitions"),
        DashboardStat(label="Models in Registry", value=str(model_count), note="All stages"),
        DashboardStat(
            label="Last Materialization",
            value=last_materialization_value,
            note="Latest run",
        ),
        DashboardStat(label="Data Freshness", value="98%", note="SLA: 95%"),
    ]

    recent_materializations = []
    if last_materialization:
        recent_runs = (
            db.query(FeatureMaterialization)
            .order_by(FeatureMaterialization.started_at.desc())
            .limit(4)
            .all()
        )
        for run in recent_runs:
            recent_materializations.append(
                MaterializationItem(
                    name=str(run.feature_id),
                    status=run.status,
                    time=run.started_at.isoformat() if run.started_at else "unknown",
                )
            )

    promotions = (
        db.query(ModelStageHistory)
        .order_by(ModelStageHistory.changed_at.desc())
        .limit(4)
        .all()
    )
    recent_promotions = [
        PromotionItem(
            model=str(promotion.model_version_id),
            stage=promotion.to_stage,
            time=promotion.changed_at.isoformat(),
        )
        for promotion in promotions
    ]

    return DashboardSummary(
        stats=stats,
        recent_materializations=recent_materializations,
        recent_promotions=recent_promotions,
    )
