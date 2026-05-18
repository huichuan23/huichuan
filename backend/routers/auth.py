"""
Simple email/password auth and profile storage.
"""
import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import User, get_db

router = APIRouter()


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, expected = stored.split("$", 2)
    except ValueError:
        return False
    actual = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(actual, expected)


def serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "profile": user.profile or {},
    }


def issue_token(user: User, db: Session) -> str:
    user.auth_token = secrets.token_urlsafe(32)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.auth_token


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")
    token = authorization.split(" ", 1)[1].strip()
    user = db.query(User).filter(User.auth_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    return user


@router.post("/auth/register")
def register(payload: AuthRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password), profile={})
    db.add(user)
    db.commit()
    db.refresh(user)
    token = issue_token(user, db)
    return {"token": token, "user": serialize_user(user)}


@router.post("/auth/login")
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = issue_token(user, db)
    return {"token": token, "user": serialize_user(user)}


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return serialize_user(user)


@router.put("/profile")
def save_profile(payload: ProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.profile = payload.profile or {}
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)
