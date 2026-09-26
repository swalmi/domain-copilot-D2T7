"""Seed the two demo accounts the quick start and 5-minute demo path rely on.

Roles must stay inside the set the API accepts (``client`` / ``corp`` in
``src/api/routes/auth.py``); ``require_role`` matches by exact string, so an
account seeded as anything else authenticates fine and is then refused by every
protected route. Passwords are local-demo credentials and must never be reused
off a developer machine.
"""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.auth import hash_password
from src.infrastructure.config import get_settings
from src.infrastructure.db.models import Base, UserModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "email": "e2ecorp@example.com",
        "password": "password123",
        "role": "corp",
    },
    {
        "email": "claimdemo@example.com",
        "password": "password123",
        "role": "client",
    },
]


async def seed_demo_users(session: AsyncSession) -> None:
    """Seed the demo corp and client accounts into PostgreSQL if missing."""

    for user_data in DEMO_USERS:
        stmt = select(UserModel).where(UserModel.email == user_data["email"])
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            # Earlier revisions seeded roles the API rejects, which left the demo
            # accounts authenticating but unusable. Reconcile on re-run.
            if existing.role != user_data["role"]:
                logger.info(
                    f"Updating demo user '{user_data['email']}' role "
                    f"'{existing.role}' -> '{user_data['role']}'."
                )
                existing.role = user_data["role"]
            else:
                logger.info(f"Demo user '{user_data['email']}' already exists.")
            continue

        new_user = UserModel(
            id=uuid.uuid4(),
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
            role=user_data["role"],
        )
        session.add(new_user)
        logger.info(
            f"Created demo user '{user_data['email']}' with role '{user_data['role']}'."
        )

    await session.commit()


async def main() -> None:
    """Initialize database tables and run user seeding script."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        await seed_demo_users(session)

    await engine.dispose()
    logger.info("Demo user seeding process completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
