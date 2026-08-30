from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Claim(BaseModel):
    """Represents an insurance claim submitted for processing."""

    id: UUID
    policy_number: str
    date_of_loss: date
    incident_description: str
    claim_amount_requested: Decimal
    status: Literal[
        "submitted",
        "processing",
        "pending_approval",
        "approved",
        "rejected",
        "refused",
    ]
