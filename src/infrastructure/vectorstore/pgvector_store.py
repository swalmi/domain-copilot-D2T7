import math
import re
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import (
    Float,
    Integer,
    and_,
    func,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.policy import CitedChunk
from src.domain.interfaces.vector_store import VectorStore
from src.infrastructure.db.models import ChunkModel, DocumentModel
from src.infrastructure.ingestion.document_loader import (
    compute_chunk_hash,
    compute_document_hash,
)

# Cap on terms contributed by one query so the tsquery stays small and cheap.
QUERY_TERM_LIMIT = 12

#: Floor for a term's IDF weight so a term present in every chunk still
#: contributes something rather than zeroing out its ts_rank contribution.
MIN_IDF = 0.05


#: English function words plus the policy boilerplate that saturates the corpus.
#: Left in, they dominate the OR query and let unrelated chunks score as hits.
KEYWORD_STOPWORDS = frozenset(
    """
    is are was were be been being am do does did doing done a an the and or but if
    of to in on at by for with from as into over under about above below between
    during through before after up down out off again further then once here there
    all any both each few more most other some such no nor not only own same so than
    too very can will just should now what which who whom whose when where why how
    it its this that these those i you he she they we me him her them my your his
    their our mine yours theirs myself yourself himself herself itself themselves
    would could may might must shall have has had having been being
    """.split()
)


def normalize_policy_identifiers(query_text: str) -> str:
    """Rewrite run-together policy numbers so Postgres splits them like the corpus.

    ``to_tsvector`` parses the corpus's "HO-3" as the two lexemes ``'ho'`` and
    ``'-3'``, but parses a question's "HO3" as the single lexeme ``'ho3'``, which
    appears nowhere in the corpus. Every "under HO3?" question therefore scored
    zero keyword matches and fell back to the dense leg alone. Inserting the
    missing hyphen makes both spellings resolve to the same lexemes.
    """
    return re.sub(r"\b([A-Za-z]{2,})(\d)\b", r"\1-\2", query_text)


def keyword_terms(query_text: str) -> list[str]:
    """Extract distinct content terms, dropping function words and short tokens.

    Stopwords carry no retrieval signal but Postgres matches them, so leaving
    them in lets a chunk containing only "the" or "under" count as a hit.

    Hyphenated runs are kept whole ("ho-3", not "ho" + "3") so that
    ``plainto_tsquery`` splits them exactly the way it split the corpus. The
    corpus lexeme is ``'-3'``; a bare ``'3'`` would match nothing.
    """
    raw = re.findall(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", normalize_policy_identifiers(query_text).lower()
    )
    terms: list[str] = []
    for token in raw:
        if len(token) > 1 and token not in KEYWORD_STOPWORDS:
            terms.append(token)
    return list(dict.fromkeys(terms))[:QUERY_TERM_LIMIT]


def keyword_idf_score(query_text: str, idf: dict[str, float] | None = None):
    """SQL expression scoring a chunk by the IDF weight of the terms it contains.

    An OR-only ``@@`` is satisfied by a single hit, and this corpus saturates
    with "policy"/"cover"/"damage" (df 500-728), so a chunk repeating one
    ubiquitous term used to outrank one covering the question's real subject.
    Weighting each hit by its inverse document frequency ranks rare,
    discriminating terms ("kitchen", df 3) above the boilerplate.

    Computed as an explicit weighted sum rather than via ``ts_rank`` weights:
    ``setweight`` is tsvector-only in PostgreSQL 16 and the weight-array
    ``ts_rank`` form rejects weights outside [0, 1].
    """
    terms = keyword_terms(query_text)
    if not terms:
        return literal(0.0)
    total = literal(0.0)
    for term in terms:
        weight = (idf or {}).get(term)
        if weight is None:
            continue
        hit = func.to_tsvector("english", ChunkModel.text).op("@@")(
            func.plainto_tsquery("english", term)
        ).cast(Integer)
        total = total + literal(weight, type_=Float) * hit
    return total


def build_keyword_query(query_text: str):
    """Build a full-text query that ORs the question's content terms.

    ``plainto_tsquery`` ANDs every token, so a real question such as
    "what consumer protections govern claims settlement practices?" matches no
    chunk at all and the keyword leg silently returns nothing, degrading
    retrieval to dense-only. ORing the significant terms restores the leg;
    ranking is handled separately by :func:`keyword_idf_score`.
    """
    terms = keyword_terms(query_text)
    if not terms:
        return func.plainto_tsquery("english", query_text)
    combined = None
    for term in terms:
        piece = func.plainto_tsquery("english", term)
        combined = piece if combined is None else combined.op("||")(piece)
    # self_group() parenthesises the chain so it binds to @@ and ts_rank.
    return combined.self_group()


def keyword_match_count(query_text: str):
    """SQL expression counting how many query terms a chunk's text contains.

    An OR-only ``@@`` is satisfied by a single hit, so a chunk matching one
    ubiquitous term is indistinguishable from one covering the question's real
    subject matter. Counting hits lets the leg demand and rank by real overlap.
    """
    terms = keyword_terms(query_text)
    if not terms:
        return literal(0)
    total = literal(0)
    for term in terms:
        # cast(bool) -> int: Postgres has no boolean + boolean operator.
        total = total + func.to_tsvector("english", ChunkModel.text).op("@@")(
            func.plainto_tsquery("english", term)
        ).cast(Integer)
    return total


def keyword_min_matches(query_text: str) -> int:
    """Minimum distinct query terms a chunk must contain to count as a hit.

    One term cannot distinguish a real match from a chunk that merely repeats a
    common word, so questions carrying two or more content terms require two.
    A single-term question cannot and accepts one.
    """
    return 1 if len(keyword_terms(query_text)) < 2 else 2


def _apply_filters(stmt, filters: dict | None):
    if not filters:
        return stmt

    conditions = []
    if filters.get("policy_id"):
        conditions.append(ChunkModel.policy_id == filters["policy_id"])
    if filters.get("policy_type"):
        conditions.append(ChunkModel.policy_type == filters["policy_type"])
    if filters.get("effective_date_before"):
        conditions.append(
            ChunkModel.effective_date <= filters["effective_date_before"]
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector implementation of the VectorStore domain interface."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize PgVectorStore with an active SQLAlchemy AsyncSession."""
        self._session = session

    async def search(
        self, query_embedding: list[float], filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using dense vector similarity embeddings."""
        stmt = select(ChunkModel, DocumentModel.filename).join(
            DocumentModel, ChunkModel.document_id == DocumentModel.id
        )
        stmt = _apply_filters(stmt, filters)
        stmt = stmt.order_by(
            ChunkModel.embedding.cosine_distance(query_embedding)
        ).limit(top_k)

        result = await self._session.execute(stmt)
        rows = result.all()

        cited_chunks: list[CitedChunk] = []
        for chunk_obj, filename in rows:
            cited_chunks.append(
                CitedChunk(
                    chunk_id=chunk_obj.id,
                    text=chunk_obj.text,
                    source_document=filename,
                    section=chunk_obj.section or "",
                    page=chunk_obj.page or 1,
                    policy_id=chunk_obj.policy_id,
                    version=chunk_obj.version,
                    effective_date=chunk_obj.effective_date,
                    chunk_type=chunk_obj.chunk_type,
                    policy_type=chunk_obj.policy_type,
                )
            )
        return cited_chunks

    async def list_policy_ids(self) -> list[str]:
        """Return the distinct policy ids that have chunks in the corpus."""
        stmt = select(ChunkModel.policy_id).distinct().order_by(ChunkModel.policy_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def top_cosine_distance(
        self, query_embedding: list[float], filters: dict
    ) -> float | None:
        """Return the smallest cosine distance to any chunk matching the filters."""
        stmt = select(
            func.min(ChunkModel.embedding.cosine_distance(query_embedding))
        )
        stmt = _apply_filters(stmt, filters)
        distance = (await self._session.execute(stmt)).scalar()
        return float(distance) if distance is not None else None

    async def _term_idf(self, terms: list[str]) -> dict[str, float]:
        """Return smoothed inverse document frequency for each query term.

        One round trip: the GIN index serves each term's document count, so
        weighting stays cheap even for a twelve-term question.
        """
        if not terms:
            return {}
        corpus_size = (
            await self._session.execute(select(func.count()).select_from(ChunkModel))
        ).scalar() or 0
        if corpus_size == 0:
            return {}
        counts = [
            select(func.count())
            .select_from(ChunkModel)
            .where(
                func.to_tsvector("english", ChunkModel.text).op("@@")(
                    func.plainto_tsquery("english", literal(term))
                )
            )
            .correlate(ChunkModel)
            .scalar_subquery()
            .label(f"df_{i}")
            for i, term in enumerate(terms)
        ]
        row = (await self._session.execute(select(*counts))).one()
        df = dict(zip(terms, row, strict=True))
        return {
            term: max(
                MIN_IDF,
                math.log((corpus_size - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5)),
            )
            for term in terms
        }

    async def keyword_search(
        self, query_text: str, filters: dict, top_k: int
    ) -> list[CitedChunk]:
        """Search for relevant policy chunks using Postgres full-text keyword matching.

        Requires multi-term overlap and ranks by IDF-weighted coverage so the
        leg contributes genuine matches instead of chunks that merely repeat a
        ubiquitous policy word.
        """
        terms = keyword_terms(query_text)
        idf = await self._term_idf(terms)
        ts_vector = func.to_tsvector("english", ChunkModel.text)
        ts_query = build_keyword_query(query_text)
        min_matches = keyword_min_matches(query_text)
        match_count = keyword_match_count(query_text)
        idf_score = keyword_idf_score(query_text, idf=idf)

        stmt = (
            select(ChunkModel, DocumentModel.filename)
            .join(DocumentModel, ChunkModel.document_id == DocumentModel.id)
            .where(
                ts_vector.op("@@")(ts_query),
                match_count >= literal(min_matches),
            )
        )
        stmt = _apply_filters(stmt, filters)
        # Rank by IDF-weighted term coverage: rare, discriminating terms
        # outweigh the ubiquitous policy boilerplate that saturates the corpus.
        stmt = stmt.order_by(idf_score.desc(), match_count.desc()).limit(top_k)

        result = await self._session.execute(stmt)
        rows = result.all()

        cited_chunks: list[CitedChunk] = []
        for chunk_obj, filename in rows:
            cited_chunks.append(
                CitedChunk(
                    chunk_id=chunk_obj.id,
                    text=chunk_obj.text,
                    source_document=filename,
                    section=chunk_obj.section or "",
                    page=chunk_obj.page or 1,
                    policy_id=chunk_obj.policy_id,
                    version=chunk_obj.version,
                    effective_date=chunk_obj.effective_date,
                    chunk_type=chunk_obj.chunk_type,
                    policy_type=chunk_obj.policy_type,
                )
            )
        return cited_chunks

    async def chunk_exists(self, content_hash: str) -> bool:
        """Check if a chunk with the specified content hash already exists in the database."""
        stmt = select(ChunkModel.id).where(ChunkModel.content_hash == content_hash)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def get_chunks_by_section(
        self, policy_id: str, version: str, section: str
    ) -> list[CitedChunk]:
        """Retrieve all chunks belonging to a specific policy version and section ordered by page."""
        stmt = (
            select(ChunkModel, DocumentModel.filename)
            .join(DocumentModel, ChunkModel.document_id == DocumentModel.id)
            .where(
                ChunkModel.policy_id == policy_id,
                ChunkModel.version == version,
                ChunkModel.section == section,
            )
            .order_by(ChunkModel.page.asc(), ChunkModel.id.asc())
        )
        res = await self._session.execute(stmt)
        rows = res.all()

        cited_chunks: list[CitedChunk] = []
        for chunk_obj, filename in rows:
            cited_chunks.append(
                CitedChunk(
                    chunk_id=chunk_obj.id,
                    text=chunk_obj.text,
                    source_document=filename,
                    section=chunk_obj.section or "",
                    page=chunk_obj.page or 1,
                    policy_id=chunk_obj.policy_id,
                    version=chunk_obj.version,
                    effective_date=chunk_obj.effective_date,
                    chunk_type=chunk_obj.chunk_type,
                    policy_type=chunk_obj.policy_type,
                )
            )
        return cited_chunks

    async def upsert(self, chunk: CitedChunk, embedding: list[float]) -> None:
        """Insert a policy chunk and its vector embedding idempotently into the store."""
        content_hash = compute_chunk_hash(chunk.text)

        if await self.chunk_exists(content_hash):
            return

        doc_id = None
        try:
            potential_uuid = UUID(chunk.source_document)
            doc_check = await self._session.execute(
                select(DocumentModel.id).where(DocumentModel.id == potential_uuid)
            )
            if doc_check.scalar_one_or_none() is not None:
                doc_id = potential_uuid
        except (ValueError, TypeError):
            pass

        if not doc_id:
            doc_stmt = select(DocumentModel).where(
                DocumentModel.filename == chunk.source_document
            )
            doc_res = await self._session.execute(doc_stmt)
            doc_obj = doc_res.scalar_one_or_none()
            if not doc_obj:
                doc_obj = DocumentModel(
                    id=uuid.uuid4(),
                    filename=chunk.source_document,
                    content_hash=compute_document_hash(
                        chunk.source_document.encode("utf-8")
                    ),
                    status="PROCESSED",
                    created_at=datetime.now(timezone.utc),
                )
                self._session.add(doc_obj)
                await self._session.flush()
            doc_id = doc_obj.id

        new_chunk = ChunkModel(
            id=chunk.chunk_id,
            document_id=doc_id,
            policy_id=chunk.policy_id,
            policy_type=getattr(chunk, "policy_type", "home"),
            version=chunk.version,
            effective_date=chunk.effective_date,
            section=chunk.section,
            chunk_type=chunk.chunk_type,
            page=chunk.page,
            text=chunk.text,
            content_hash=content_hash,
            embedding=embedding,
        )
        self._session.add(new_chunk)
        await self._session.commit()
