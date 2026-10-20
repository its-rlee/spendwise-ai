
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class TransactionCreate(BaseModel):
    merchant: str = Field(
        min_length=1,
        max_length=255
    )
    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2
    )
    category: str = Field(
        default="Uncategorized",
        min_length=1,
        max_length=100
    )
    transaction_date: date | None = None
    currency: str = Field(
        default="USD",
        pattern=r"^[A-Z]{3}$"
    )

    @field_validator("merchant", "category")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value


class TransactionRead(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: Literal["debit", "credit"] = "debit"


class TransactionUpdate(BaseModel):
    category: str = Field(
        min_length=1,
        max_length=100
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Category cannot be empty")

        return value
