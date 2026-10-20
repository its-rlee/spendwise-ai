
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    source_index: int

    merchant: str | None
    amount: Decimal | None
    direction: str | None
    transaction_date: date | None
    currency: str | None

    review_reasons: list[str]
    status: str


class TransactionApproval(BaseModel):
    merchant: str = Field(
        min_length=1,
        max_length=255,
    )

    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    transaction_date: date

    direction: Literal["debit", "credit"]

    currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )

    category: str = Field(
        default="Uncategorized",
        min_length=1,
        max_length=100,
    )

    confirm_similar: bool = False

    @field_validator("merchant", "category")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = " ".join(value.split())

        if not value:
            raise ValueError(
                "Value cannot be blank"
            )

        return value

class DraftRejection(BaseModel):
    reason: str = Field(
        min_length=5,
        max_length=500,
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 5:
            raise ValueError(
                "Provide a reason for rejection"
            )

        return value
