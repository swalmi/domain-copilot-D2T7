"""Populate ``ChunkModel.section`` for chunks stored before section derivation.

The loader used to leave ``section`` empty because it required a ``Title``
ancestor via ``parent_id``, which the installed ``langchain_unstructured`` never
provides. With ``section`` empty, ``expand_to_parent_sections`` took its
fallthrough branch for 1956 of 1958 chunks and returned the same single fragment,
so the LLM never saw a parent section.

Re-ingesting is not an option: the current extractor version returns elements the
loader cannot read, which would overwrite good text with empty strings. This
backfills the column in place from the text already stored, using the same
:func:`section_key_for` rule the loader now applies, so both paths agree.

Idempotent: re-running rewrites the same values. Use ``--dry-run`` to preview.
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.db.models import ChunkModel  # noqa: E402
from src.infrastructure.ingestion.section_titles import section_key_for  # noqa: E402


async def backfill(db_session: AsyncSession, dry_run: bool = False) -> tuple[int, int]:
    """Return (rows_examined, rows_changed) after filling in empty sections."""
    rows = (
        await db_session.execute(
            select(ChunkModel.id, ChunkModel.text, ChunkModel.page).where(
                func.coalesce(ChunkModel.section, "") == ""
            )
        )
    ).all()

    changed = 0
    for chunk_id, text, page in rows:
        section = section_key_for(text, page)
        if not dry_run:
            await db_session.execute(
                update(ChunkModel)
                .where(ChunkModel.id == chunk_id)
                .values(section=section)
            )
        changed += 1

    if not dry_run:
        await db_session.commit()
    return len(rows), changed


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args()

    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        raise SystemExit("DATABASE_URL is not set")
    # The async driver is psycopg3; a bare postgresql:// URL would import psycopg2.
    url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(url)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        examined, changed = await backfill(session, dry_run=args.dry_run)
        total = (
            await session.execute(select(func.count()).select_from(ChunkModel))
        ).scalar()
        still_empty = (
            await session.execute(
                select(func.count())
                .select_from(ChunkModel)
                .where(func.coalesce(ChunkModel.section, "") == "")
            )
        ).scalar()
        print(f"chunks total          : {total}")
        print(f"rows examined         : {examined}")
        print(f"rows {'would update' if args.dry_run else 'updated'} : {changed}")
        print(f"still empty           : {still_empty}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
