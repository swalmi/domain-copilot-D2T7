import sys
import argparse

sys.path.insert(0, "/home/swalmi/domain-copilot-D2T7")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.infrastructure.config import get_settings
from src.infrastructure.db.models import ChunkModel


async def read_chunks(policy_id: str) -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(
            select(ChunkModel)
            .where(ChunkModel.policy_id == policy_id)
            .order_by(ChunkModel.page, ChunkModel.id)
        )
        chunks = result.scalars().all()
        for i, c in enumerate(chunks):
            print(f"[{i}] page={c.page} | section={c.section or '(none)'} | type={c.chunk_type}")
            print(c.text.strip())
            print("-" * 80)
        print(f"\nTotal chunks: {len(chunks)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-id", required=True)
    args = parser.parse_args()
    import asyncio
    asyncio.run(read_chunks(args.policy_id))
