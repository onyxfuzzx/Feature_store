import hashlib
import secrets
from uuid import UUID

from app.api.deps import get_current_user, get_db
from app.api.pagination import page, page_limit, page_offset
from app.db.models.core import APIKey, User
from app.schemas.api_keys import APIKeyCreate, APIKeyCreateOut, APIKeyOut
from app.services.audit import log_audit
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[APIKeyOut])
def list_api_keys(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all active API keys for the current user.
    """
    return page(
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id, APIKey.is_active.is_(True))
        .order_by(APIKey.created_at.desc(), APIKey.id.desc()),
        response,
        limit,
        offset,
    )


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
    db.flush()

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_API_KEY",
        entity_type="api_key",
        entity_id=db_key.id,
        payload={"name": db_key.name},
        commit=False,
    )

    db.commit()
    db.refresh(db_key)
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

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REVOKE_API_KEY",
        entity_type="api_key",
        entity_id=db_key.id,
        payload={"name": db_key.name},
        commit=False,
    )
    db.commit()
    return None
