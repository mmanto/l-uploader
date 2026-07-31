import os

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")
COOKIE_NAME = "luploader_session"
COOKIE_MAX_AGE = 60 * 60 * 8  # 8 horas

signer = URLSafeTimedSerializer(SECRET_KEY)


def sign(username: str) -> str:
    return signer.dumps(username)


def verify(token: str) -> str | None:
    try:
        return signer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    return bool(verify(token))


def check_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USER and password == ADMIN_PASS
