from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.models import User, Role
from backend.dependencies import get_db
from backend.security import get_current_user, verify_password, hash_password

router = APIRouter(prefix="/api/account", tags=["Account"])


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def serialize_user(user: User, db: Session):
    role = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "role": role.role_name if role else None,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
    }


@router.get("/me")
def get_my_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return serialize_user(current_user, db)


@router.put("/profile")
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.full_name = payload.full_name
    current_user.avatar_url = payload.avatar_url
    current_user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Cập nhật hồ sơ thành công",
        "user": serialize_user(current_user, db)
    }


@router.put("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu hiện tại không chính xác"
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": "Đổi mật khẩu thành công"
    }