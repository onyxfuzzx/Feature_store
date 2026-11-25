from app.api.deps import get_current_user, get_user_roles
from app.core.security import create_access_token, verify_password
from app.db.models.core import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenOut
from app.schemas.common import MessageOut
from app.schemas.users import UserOut
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(subject=str(user.id))
    roles = get_user_roles(db, user.id)
    user_out = UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_active=user.is_active,
        roles=roles,
        created_at=user.created_at,
    )
    return TokenOut(access_token=access_token, user=user_out)


@router.post("/logout", response_model=MessageOut, status_code=status.HTTP_200_OK)
def logout():
    return MessageOut(message="Logout placeholder")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = get_user_roles(db, current_user.id)
    return UserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        is_active=current_user.is_active,
        roles=roles,
        created_at=current_user.created_at,
    )
