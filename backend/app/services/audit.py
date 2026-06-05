import json
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.core import AuditLog

def log_audit(
    db: Session,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None
) -> AuditLog:
    """
    Utility to record actions to core.audit_log for RBAC and audit compliance.
    """
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload_json=json.dumps(payload) if payload else None
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
