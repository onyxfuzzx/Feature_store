from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_user_roles, require_roles, get_current_user
from app.core import roles
from app.core.security import hash_password
from app.db.models.core import Role, User, UserRole, AuditLog
from app.db.session import get_db
from app.schemas.users import UserCreate, UserOut
from app.schemas.audit import AuditLogOut
from app.services.audit import log_audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles(roles.ADMIN))],
)
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    results = []
    for user in users:
        results.append(
            UserOut(
                id=user.id,
                name=user.name,
                email=user.email,
                is_active=user.is_active,
                roles=get_user_roles(db, user.id),
                created_at=user.created_at,
            )
        )
    return results


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(roles.ADMIN))],
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    role_rows = db.query(Role).filter(Role.name.in_(payload.roles)).all()
    if len(role_rows) != len(payload.roles):
        raise HTTPException(status_code=400, detail="Invalid role name")

    for role_row in role_rows:
        db.add(UserRole(user_id=user.id, role_id=role_row.id))

    db.commit()

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_USER",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email, "roles": payload.roles},
    )

    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_active=user.is_active,
        roles=get_user_roles(db, user.id),
        created_at=user.created_at,
    )


@router.get(
    "/audit-logs",
    response_model=list[AuditLogOut],
    dependencies=[Depends(require_roles(roles.ADMIN))],
)
def list_audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()

