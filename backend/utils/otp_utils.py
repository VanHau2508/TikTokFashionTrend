import os
import random
import hashlib
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_secret_key")


def generate_otp(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def hash_otp(otp: str, email: str, purpose: str) -> str:
    raw = f"{otp}:{email.lower()}:{purpose}:{SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_otp(plain_otp: str, otp_hash: str, email: str, purpose: str) -> bool:
    return hash_otp(plain_otp, email, purpose) == otp_hash