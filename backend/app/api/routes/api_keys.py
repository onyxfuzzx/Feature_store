import secrets
import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db.models.core import APIKey, User
from app.schemas.api_keys import APIKeyCreate, APIKeyOut, APIKeyCreateOut
from app.services.audit import log_audit

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

@router.get("", response_model=list[APIKeyOut])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all active API keys for the current user.
    """
    return db.query(APIKey).filter(APIKey.user_id == current_user.id, APIKey.is_active == True).all()

@router.post("", response_model=APIKeyCreateOut, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new API key. The plain text key will ONLY be returned once.
    """
    raw_key = f"fo_{secrets.token_urlsafe(32)}"
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    db_key = APIKey(
        user_id=current_user.id,
        name=payload.name,
        key_hash=hashed_key,
        is_active=True,
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_API_KEY",
        entity_type="api_key",
        entity_id=db_key.id,
        payload={"name": db_key.name},
    )

    return APIKeyCreateOut(
        id=db_key.id,
        user_id=db_key.user_id,
        name=db_key.name,
        is_active=db_key.is_active,
        created_at=db_key.created_at,
        plain_key=raw_key,
    )

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke (deactivate) an API key.
    """
    db_key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == current_user.id).first()
    if not db_key:
        raise HTTPException(status_code=404, detail="API key not found")

    db_key.is_active = False
    db.commit()

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REVOKE_API_KEY",
        entity_type="api_key",
        entity_id=db_key.id,
        payload={"name": db_key.name},
    )
    return None
