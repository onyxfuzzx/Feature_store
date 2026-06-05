from datetime import datetime
from uuid import UUID
from app.schemas.common import ORMBase

class AuditLogOut(ORMBase):
    id: UUID
    actor_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: str
    payload_json: str | None = None
    created_at: datetime
