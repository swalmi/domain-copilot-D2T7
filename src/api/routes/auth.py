from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.infrastructure.config import get_settings
from src.infrastructure.db.models import UserModel

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """Data transfer object for user login credentials."""

    email: EmailStr
    password: str


def hash_password(password: str) -> str:
    """Generate salted bcrypt hash for raw user password string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify raw plaintext password against stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )



def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Encode user claims into a signed JWT access token with 24-hour expiration default."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    settings = get_settings()
    return jwt.encode(
        to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Authenticate user credentials and set httpOnly JWT session cookie."""
    stmt = select(UserModel).where(UserModel.email == payload.email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=86400,
    )

    return {
        "status": "success",
        "user": {"id": str(user.id), "email": user.email, "role": user.role},
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response) -> dict[str, str]:
    """Clear active user session by deleting access token cookie."""
    response.delete_cookie(key="access_token", httponly=True, samesite="strict")
    return {"status": "logged_out"}
