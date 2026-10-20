
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReceiptItem(BaseModel):
    name: str
    price: Decimal | None = Field(
        default=None,
        ge=0,
    )


class ReceiptExtraction(BaseModel):
    kind: Literal["receipt"] = "receipt"

    merchant: str | None = None
    purchase_date: date | None = None
    currency: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
    )

    subtotal: Decimal | None = Field(
        default=None,
        ge=0,
    )
    tax: Decimal | None = Field(
        default=None,
        ge=0,
    )
    tax_rate_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    total: Decimal | None = Field(
        default=None,
        ge=0,
    )

    items: list[ReceiptItem] = Field(
        default_factory=list
    )

    needs_review: bool = False
    review_reasons: list[str] = Field(
        default_factory=list
    )
    @model_validator(mode="before")
    @classmethod
    def normalize_tax_rate(cls, data):
        if not isinstance(data, dict):
            return data

        data = data.copy()
        tax = data.get("tax")

        if isinstance(tax, str) and tax.strip().endswith("%"):
            rate = tax.strip().removesuffix("%").strip()

            # Keep the tax amount unknown.
            data["tax"] = None

            try:
                data["tax_rate_percent"] = str(
                    Decimal(rate)
                )
            except Exception:
                pass

            data["needs_review"] = True

            reasons = data.get("review_reasons")
            if not isinstance(reasons, list):
                reasons = []

            data["review_reasons"] = [
                *reasons,
                "Tax rate supplied instead of tax amount",
            ]

        return data



class StatementTransaction(BaseModel):
    posted_date: date | None = None
    description: str | None = None

    amount: Decimal | None = Field(
        default=None,
        gt=0,
    )

    direction: Literal[
        "debit", "credit", "unknown"
    ] = "unknown"


class StatementExtraction(BaseModel):
    kind: Literal["statement"] = "statement"

    bank_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None

    transactions: list[StatementTransaction] = Field(
        default_factory=list
    )

    needs_review: bool = False
    review_reasons: list[str] = Field(
        default_factory=list
    )
