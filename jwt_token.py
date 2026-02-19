import jwt
from datetime import datetime, timedelta

SECRET_KEY = "a8f9c2d7$KJH@#9xP0qL!mZ8w3E1"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30


def create_jwt(payload: dict) -> str:
    payload_copy = payload.copy()
    payload_copy["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload_copy["iat"] = datetime.utcnow()

    token = jwt.encode(payload_copy, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_jwt(token: str) -> dict:
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return decoded
