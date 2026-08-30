from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PolicyVersion(BaseModel):
    """Represents a specific version and effective period of an insurance policy."""

    policy_id: str
    version: str
    effective_date: date
    policy_type: Literal["auto", "home", "commercial_property", "regulatory_guidance", "liability"] | str


class CitedChunk(BaseModel):
    """Represents a cited excerpt from a policy document used during claim adjudication."""

    chunk_id: UUID
    text: str
    source_document: str
    section: str
    page: int
    policy_id: str
    version: str
    effective_date: date
    chunk_type: Literal["narrative", "table"] | str
    policy_type: Literal["auto", "home", "commercial_property", "regulatory_guidance", "liability"] | str = "home"
