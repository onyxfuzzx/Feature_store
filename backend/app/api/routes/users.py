from app.api.deps import get_current_user, get_user_roles, require_roles
from app.api.pagination import page, page_limit, page_offset
from app.core import roles
from app.core.security import hash_password
from app.db.models.core import AuditLog, Role, User, UserRole
from app.db.session import get_db
from app.schemas.audit import AuditLogOut
from app.schemas.users import UserCreate, UserOut
from app.services.audit import log_audit
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles(roles.ADMIN))],
)
def list_users(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    users = page(
        db.query(User).order_by(User.created_at.desc(), User.id.desc()), response, limit, offset
    )
    grouped = {user.id: [] for user in users}
    if users:
        for user_id, role in (
            db.query(UserRole.user_id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.user_id.in_(grouped))
            .all()
        ):
            grouped[user_id].append(role)
    results = []
    for user in users:
        results.append(
            UserOut(
                id=user.id,
                name=user.name,
                email=user.email,
                is_active=user.is_active,
                roles=grouped[user.id],
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

    role_rows = db.query(Role).filter(Role.name.in_(payload.roles)).all()
    if (
        not payload.roles
        or len(payload.roles) != len(set(payload.roles))
        or len(role_rows) != len(payload.roles)
    ):
        raise HTTPException(400, "Invalid role name")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    for role_row in role_rows:
        db.add(UserRole(user_id=user.id, role_id=role_row.id))

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="CREATE_USER",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email, "roles": payload.roles},
        commit=False,
    )

    db.commit()
    db.refresh(user)
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
def list_audit_logs(
    response: Response,
    limit: int = page_limit(),
    offset: int = page_offset(),
    db: Session = Depends(get_db),
):
    return page(
        db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()),
        response,
        limit,
        offset,
    )
