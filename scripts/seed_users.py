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
        "email": "handler@domaincopilot.com",
        "password": "HandlerPass123!",
        "role": "claims_handler",
    },
    {
        "email": "adjuster@domaincopilot.com",
        "password": "AdjusterPass123!",
        "role": "adjuster",
    },
]


async def seed_demo_users(session: AsyncSession) -> None:
    """Seed demo claims handler and adjuster accounts into PostgreSQL database if missing."""
    for user_data in DEMO_USERS:
        stmt = select(UserModel).where(UserModel.email == user_data["email"])
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
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
