"""Caller holds the model row lock; stages, history and audit share its transaction."""
from app.db.models.model_registry import ModelVersion, ModelStageHistory
from app.services.audit import log_audit


def transition(db, version, stage, actor_id):
    if stage == "Production":
        previous = db.query(ModelVersion).filter(ModelVersion.model_id == version.model_id,
                                                 ModelVersion.id != version.id,
                                                 ModelVersion.stage == "Production").all()
        for incumbent in previous:
            transition(db, incumbent, "Archived", actor_id)
        db.flush()  # release the partial unique index before setting the new Production version
    if version.stage != stage:
        old = version.stage
        version.stage = stage
        db.add(ModelStageHistory(model_version_id=version.id, from_stage=old, to_stage=stage, changed_by=actor_id))
        log_audit(db, actor_id, "PROMOTE_MODEL_VERSION", "model_version", version.id,
                  {"from_stage": old, "to_stage": stage}, commit=False)
