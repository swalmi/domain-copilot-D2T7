from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import UserPayload, get_current_user, get_db_session, require_role
from src.api.limiter import limiter
from src.infrastructure.config import get_settings
from src.infrastructure.db.models import UserModel

router = APIRouter(prefix="/auth", tags=["Authentication"])

VALID_ROLES = {"client", "corp"}


class SignupRequest(BaseModel):
    """Data transfer object for new user account registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["client", "corp"]


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


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    payload: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Register a new client or corp user, hash password, and start authenticated session."""
    existing = await session.execute(
        select(UserModel).where(UserModel.email == payload.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = UserModel(
        id=uuid4(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    await session.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return {
        "status": "success",
        "user": {"id": str(user.id), "email": user.email, "role": user.role},
    }


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Authenticate user credentials and set httpOnly JWT session cookie with rate limiting."""
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
        samesite="lax",
        max_age=86400,
    )

    return {
        "status": "success",
        "user": {"id": str(user.id), "email": user.email, "role": user.role},
    }


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    current_user: UserPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Return currently authenticated user profile derived from the validated JWT session cookie."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get("/clients-count", status_code=status.HTTP_200_OK)
async def get_clients_count(
    session: AsyncSession = Depends(get_db_session),
    current_user: UserPayload = Depends(require_role("corp")),
) -> dict[str, int]:
    """Return the total number of registered client (policyholder) accounts."""
    stmt = select(UserModel).where(UserModel.role == "client")
    res = await session.execute(stmt)
    return {"client_count": len(res.scalars().all())}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response) -> dict[str, str]:
    """Clear active user session by deleting access token cookie."""
    # Use same attributes as cookie setting when deleting
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return {"status": "logged_out"}
