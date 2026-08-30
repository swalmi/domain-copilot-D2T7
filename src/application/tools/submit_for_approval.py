from uuid import UUID

from src.application.contracts.adjudication_draft import AdjudicationDraft
from src.domain.interfaces.claim_repository import ClaimRepository


async def submit_for_approval(
    draft: AdjudicationDraft, claim_id: UUID, claim_repo: ClaimRepository
) -> UUID:
    """Side-effecting tool submitting an adjudication recommendation draft to pending_approval status ONLY."""
    claim = await claim_repo.get_by_id(claim_id)
    if claim:
        claim.status = "pending_approval"
        await claim_repo.save(claim)
    return claim_id
