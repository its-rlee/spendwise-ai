
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
    receipt_items: list[dict] = Field(
        default_factory=list,
    )

    items_reviewed: bool = False

    receipt_subtotal: Decimal | None = None


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

    confirm_item_mismatch: bool = False

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

class ReceiptItemEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=255,
    )

    amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    category: str = Field(
        default="Uncategorized",
        min_length=1,
        max_length=100,
    )

    @field_validator("name", "category")
    @classmethod
    def strip_and_validate(cls, value: str):
        value = " ".join(value.split())

        if not value:
            raise ValueError("Value cannot be blank")

        return value


    source_line_index: int | None = Field(
        default=None,
        ge=0,
    )

    raw_description: str | None = Field(
        default=None,
        max_length=255,
    )

    store_item_code: str | None = Field(
        default=None,
        max_length=64,
    )


class ReceiptItemsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReceiptItemEdit] = Field(
        max_length=100,
    )
