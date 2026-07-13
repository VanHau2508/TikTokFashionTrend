from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.security import hash_password, require_admin
from database.models import Role, User

router = APIRouter(prefix="/api/admin", tags=["Admin Users"])

SUPER_ADMIN_USERNAME = "admin123"


class AdminCreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None
    role_name: str = "user"
    is_active: bool = True
    is_email_verified: bool = True


class AdminUpdateUserRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    role_name: str | None = None
    is_active: bool | None = None
    is_email_verified: bool | None = None


class AdminUserStatusRequest(BaseModel):
    is_active: bool


def admin_serialize_user(user: User, role: Role | None = None):
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": getattr(user, "avatar_url", None),
        "role": role.role_name if role else None,
        "role_id": user.role_id,
        "is_active": user.is_active,
        "is_email_verified": getattr(user, "is_email_verified", False),
        "created_at": user.created_at,
        "updated_at": getattr(user, "updated_at", None),
        "last_login": user.last_login,
    }


def get_user_role_name(db: Session, user: User) -> str:
    role = db.query(Role).filter(Role.role_id == user.role_id).first()
    return role.role_name.lower() if role and role.role_name else "user"


def is_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def is_target_super_admin(user: User) -> bool:
    return user.username == SUPER_ADMIN_USERNAME


def ensure_can_manage_user(
    db: Session,
    current_user: User,
    target_user: User,
    action: str = "manage",
):
    if is_target_super_admin(target_user):
        raise HTTPException(
            status_code=403,
            detail="Tài khoản Super Admin admin123 không thể bị chỉnh sửa hoặc khóa.",
        )

    current_role = get_user_role_name(db, current_user)
    target_role = get_user_role_name(db, target_user)

    if current_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền quản trị.",
        )

    if is_super_admin(current_user):
        return True

    if target_role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin thường không được chỉnh sửa hoặc khóa tài khoản admin khác.",
        )

    return True


def ensure_can_assign_role(
    db: Session,
    current_user: User,
    role_name: str,
):
    role_name = (role_name or "user").lower()

    if role_name == "admin" and not is_super_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Chỉ Super Admin admin123 mới được cấp quyền admin.",
        )

    return True


@router.get("/users")
def get_admin_users(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    rows = (
        db.query(User, Role)
        .outerjoin(Role, User.role_id == Role.role_id)
        .order_by(desc(User.created_at))
        .limit(limit)
        .all()
    )

    return [admin_serialize_user(user, role) for user, role in rows]


@router.post("/users")
def admin_create_user(
    payload: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ensure_can_assign_role(db, current_user, payload.role_name)

    existing_user = db.query(User).filter(
        or_(
            User.username == payload.username,
            User.email == payload.email,
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username hoặc email đã tồn tại",
        )

    role = db.query(Role).filter(Role.role_name == payload.role_name).first()

    if not role:
        raise HTTPException(
            status_code=400,
            detail="Role không tồn tại",
        )

    now = datetime.now(timezone.utc)

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.role_id,
        is_active=payload.is_active,
        is_email_verified=payload.is_email_verified,
        email_verified_at=now if payload.is_email_verified else None,
        created_at=now,
        updated_at=now,
        last_login=now,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Tạo tài khoản thành công",
        "user": admin_serialize_user(new_user, role),
    }


@router.put("/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy user",
        )

    ensure_can_manage_user(db, current_user, user, action="update")

    if payload.username and payload.username != user.username:
        existing = db.query(User).filter(User.username == payload.username).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username đã tồn tại",
            )

        user.username = payload.username

    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(User.email == payload.email).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email đã tồn tại",
            )

        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if hasattr(user, "avatar_url") and payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url

    if payload.role_name:
        ensure_can_assign_role(db, current_user, payload.role_name)

        role = db.query(Role).filter(Role.role_name == payload.role_name).first()

        if not role:
            raise HTTPException(
                status_code=400,
                detail="Role không tồn tại",
            )

        user.role_id = role.role_id

    if payload.is_active is not None:
        if user.user_id == current_user.user_id and payload.is_active is False:
            raise HTTPException(
                status_code=400,
                detail="Bạn không thể tự khóa tài khoản của chính mình",
            )

        user.is_active = payload.is_active

    if payload.is_email_verified is not None:
        user.is_email_verified = payload.is_email_verified
        user.email_verified_at = (
            datetime.now(timezone.utc)
            if payload.is_email_verified
            else None
        )

    if hasattr(user, "updated_at"):
        user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    role = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "message": "Cập nhật user thành công",
        "user": admin_serialize_user(user, role),
    }


@router.patch("/users/{user_id}/status")
def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy user",
        )

    if user.user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn không thể tự khóa tài khoản của chính mình",
        )

    ensure_can_manage_user(db, current_user, user, action="status")

    user.is_active = payload.is_active

    if hasattr(user, "updated_at"):
        user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    role = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "message": "Đã mở khóa tài khoản" if payload.is_active else "Đã khóa tài khoản",
        "user": admin_serialize_user(user, role),
    }


@router.get("/users/advanced")
def get_users_advanced(
    search: str | None = None,
    role: str | None = None,
    verified: str | None = None,
    active: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(User, Role).outerjoin(Role, User.role_id == Role.role_id)

    if search:
        keyword = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(User.username).like(keyword),
                func.lower(User.email).like(keyword),
                func.lower(User.full_name).like(keyword),
            )
        )

    if role and role != "all":
        query = query.filter(func.lower(Role.role_name) == role.lower())

    if verified == "verified":
        query = query.filter(User.is_email_verified == True)

    if verified == "unverified":
        query = query.filter(User.is_email_verified == False)

    if active == "active":
        query = query.filter(User.is_active == True)

    if active == "locked":
        query = query.filter(User.is_active == False)

    rows = query.order_by(desc(User.created_at)).limit(limit).all()

    return [
        admin_serialize_user(user, user_role)
        for user, user_role in rows
    ]
