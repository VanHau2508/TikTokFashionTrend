import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models import User, EmailOTP, Role
from backend.dependencies import get_db
from backend.security import hash_password
from backend.utils.otp_utils import generate_otp, hash_otp, verify_otp
from backend.services.email_service import send_otp_email

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, HTTPException, status

from backend.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str

class ResendOTPRequest(BaseModel):
    email: EmailStr
    purpose: str = "verify_email"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

def create_and_send_otp(
    db: Session,
    user: User,
    email: str,
    purpose: str
):
    now = datetime.now(timezone.utc)

    old_otps = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.purpose == purpose,
        EmailOTP.used_at == None
    ).all()

    for item in old_otps:
        item.used_at = now

    otp = generate_otp()
    otp_hash = hash_otp(otp, email, purpose)

    otp_record = EmailOTP(
        user_id=user.user_id,
        email=email,
        purpose=purpose,
        otp_hash=otp_hash,
        expires_at=now + timedelta(minutes=10),
        attempts=0,
        created_at=now
    )

    db.add(otp_record)
    db.commit()

    send_otp_email(email, otp, purpose)

    dev_mode = os.getenv("DEV_MODE_SHOW_OTP", "false").lower() == "true"

    if dev_mode:
        return otp

    return None

def get_valid_otp_record(
    db: Session,
    email: str,
    purpose: str
):
    now = datetime.now(timezone.utc)

    return db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.purpose == purpose,
        EmailOTP.used_at == None,
        EmailOTP.expires_at > now
    ).order_by(
        EmailOTP.created_at.desc()
    ).first()

@router.post("/register")
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        or_(
            User.username == payload.username,
            User.email == payload.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username hoặc email đã tồn tại"
        )

    user_role = db.query(Role).filter(Role.role_name == "user").first()

    if not user_role:
        user_role = Role(role_name="user")
        db.add(user_role)
        db.commit()
        db.refresh(user_role)

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=user_role.role_id,
        is_active=True,
        is_email_verified=False,
        created_at=datetime.now(timezone.utc),
        last_login=datetime.now(timezone.utc)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    dev_otp = create_and_send_otp(
        db=db,
        user=new_user,
        email=new_user.email,
        purpose="verify_email"
    )

    response = {
        "message": "Đăng ký thành công. Vui lòng kiểm tra email để lấy mã OTP.",
        "email": new_user.email
    }

    if dev_otp:
        response["dev_otp"] = dev_otp

    return response

@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    if user.is_email_verified:
        return {
            "message": "Email đã được xác thực trước đó"
        }

    otp_record = get_valid_otp_record(
        db=db,
        email=payload.email,
        purpose="verify_email"
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="OTP không tồn tại hoặc đã hết hạn")

    if otp_record.attempts >= 5:
        raise HTTPException(status_code=400, detail="Bạn đã nhập sai OTP quá nhiều lần")

    if not verify_otp(
        plain_otp=payload.otp,
        otp_hash=otp_record.otp_hash,
        email=payload.email,
        purpose="verify_email"
    ):
        otp_record.attempts = (otp_record.attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="OTP không chính xác")

    now = datetime.now(timezone.utc)

    otp_record.used_at = now
    user.is_email_verified = True
    user.email_verified_at = now

    db.commit()

    return {
        "message": "Xác thực email thành công"
    }

@router.post("/resend-email-otp")
def resend_email_otp(
    payload: ResendOTPRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    dev_otp = create_and_send_otp(
        db=db,
        user=user,
        email=user.email,
        purpose=payload.purpose
    )

    response = {
        "message": "Đã gửi lại mã OTP về email"
    }

    if dev_otp:
        response["dev_otp"] = dev_otp

    return response
@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    email = payload.email.lower().strip()

    if not email.endswith("@gmail.com"):
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập đúng địa chỉ Gmail"
        )

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email này chưa được đăng ký trong hệ thống"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản này đã bị khóa hoặc chưa được kích hoạt"
        )

    dev_otp = create_and_send_otp(
        db=db,
        user=user,
        email=user.email,
        purpose="forgot_password"
    )

    response = {
        "message": "Mã OTP đặt lại mật khẩu đã được gửi đến Gmail của bạn."
    }

    if dev_otp:
        response["dev_otp"] = dev_otp

    return response

@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    otp_record = get_valid_otp_record(
        db=db,
        email=payload.email,
        purpose="forgot_password"
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="OTP không tồn tại hoặc đã hết hạn")

    if otp_record.attempts >= 5:
        raise HTTPException(status_code=400, detail="Bạn đã nhập sai OTP quá nhiều lần")

    if not verify_otp(
        plain_otp=payload.otp,
        otp_hash=otp_record.otp_hash,
        email=payload.email,
        purpose="forgot_password"
    ):
        otp_record.attempts = (otp_record.attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="OTP không chính xác")

    otp_record.used_at = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)

    db.commit()

    return {
        "message": "Đặt lại mật khẩu thành công"
    }
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    support_email = os.getenv("SYSTEM_SUPPORT_EMAIL", "levanhau2019cm@gmail.com")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tài khoản hoặc mật khẩu"
        )

    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tài khoản hoặc mật khẩu"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=f"Tài khoản của bạn đã bị khóa. Vui lòng liên hệ {support_email} để được hỗ trợ mở khóa."
        )
    
    if not user.is_email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email chưa được xác thực. Vui lòng kiểm tra email để nhập OTP."
        )

    role = db.query(Role).filter(Role.role_id == user.role_id).first()
    role_name = role.role_name if role else "user"

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    access_token = create_access_token({
        "user_id": user.user_id,
        "username": user.username,
        "role": role_name
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": role_name
        }
    }


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    return {
        "message": "Đăng xuất thành công. Frontend hãy xóa access_token khỏi localStorage/sessionStorage."
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = db.query(Role).filter(Role.role_id == current_user.role_id).first()

    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": role.role_name if role else None
    }