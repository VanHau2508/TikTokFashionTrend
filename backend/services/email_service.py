import os
import smtplib
import logging
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "TikTokFashionTrend")


def send_email(to_email: str, subject: str, html_content: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("⚠️ SMTP chưa được cấu hình. Email không được gửi thật.")
        logger.warning(f"To: {to_email}")
        logger.warning(f"Subject: {subject}")
        logger.warning(html_content)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email

    msg.set_content("Email này yêu cầu trình đọc hỗ trợ HTML.")
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    return True


def send_otp_email(to_email: str, otp: str, purpose: str):
    if purpose == "verify_email":
        title = "Xác thực email FashionTrend AI"
        message = "Mã OTP dùng để xác thực tài khoản của bạn."
    elif purpose == "forgot_password":
        title = "Đặt lại mật khẩu FashionTrend AI"
        message = "Mã OTP dùng để đặt lại mật khẩu của bạn."
    else:
        title = "Mã OTP FashionTrend AI"
        message = "Mã OTP xác thực yêu cầu của bạn."

    html = f"""
    <div style="font-family:Arial,sans-serif;background:#f8fafc;padding:32px;">
        <div style="max-width:520px;margin:auto;background:white;border-radius:20px;padding:28px;border:1px solid #e5e7eb;">
            <h2 style="color:#1F283C;margin-bottom:8px;">{title}</h2>
            <p style="color:#667D98;font-size:15px;">{message}</p>

            <div style="margin:24px 0;background:#FFF2F3;color:#FE2062;border-radius:16px;padding:20px;text-align:center;font-size:34px;font-weight:800;letter-spacing:8px;">
                {otp}
            </div>

            <p style="color:#667D98;font-size:14px;">
                Mã OTP có hiệu lực trong 10 phút. Không chia sẻ mã này cho bất kỳ ai.
            </p>

            <p style="color:#99A8BA;font-size:12px;margin-top:24px;">
                FashionTrend AI - TikTok Fashion Analytics Platform
            </p>
        </div>
    </div>
    """

    return send_email(to_email, title, html)