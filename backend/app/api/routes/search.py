from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core import roles
from app.db.models.feature_store import FeatureDefinition
from app.db.models.model_registry import Model
from app.db.session import get_db

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", dependencies=[Depends(require_roles(roles.ADMIN, roles.ML_ENGINEER, roles.DATA_SCIENTIST, roles.ANALYST))])
def search(q: str | None = None, db: Session = Depends(get_db)):
    if not q:
        return {"query": q, "features": [], "models": []}

    features = (
        db.query(FeatureDefinition)
        .filter(FeatureDefinition.name.ilike(f"%{q}%"))
        .limit(10)
        .all()
    )
    models = db.query(Model).filter(Model.name.ilike(f"%{q}%")).limit(10).all()

    return {
        "query": q,
        "features": [{"id": str(f.id), "name": f.name} for f in features],
        "models": [{"id": str(m.id), "name": m.name} for m in models],
    }
