import hashlib
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.core import APIKey, Role, User, UserRole
from app.db.session import get_db

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> User:
    # 1. Try Token
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            subject = payload.get("sub")
            if subject:
                user_id = uuid.UUID(subject)
                user = db.get(User, user_id)
                if user and user.is_active:
                    return user
        except (JWTError, ValueError):
            pass

    # 2. Try API Key
    if api_key:
        hashed_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        db_key = db.query(APIKey).filter(APIKey.key_hash == hashed_key, APIKey.is_active == True).first()
        if db_key:
            user = db.get(User, db_key.user_id)
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_roles(db: Session, user_id: uuid.UUID) -> list[str]:
    roles = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    return [row[0] for row in roles]


def require_roles(*allowed: str):
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not allowed:
            return user

        user_roles = set(get_user_roles(db, user.id))
        if not user_roles.intersection(set(allowed)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency
