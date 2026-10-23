"""Validated finance query plans. The model never supplies SQL or user IDs."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FinanceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["transactions", "items"]
    action: Literal["list", "aggregate"]
    group_by: Literal["none", "merchant", "category", "product", "month", "weekday"] = "none"
    measure: Literal["sum", "count", "average", "minimum", "maximum"] = "sum"
    sort: Literal["latest", "oldest", "highest", "lowest", "alphabetical"] = "latest"
    direction: Literal["debit", "credit", "both"] = "debit"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    date_from: date | None = None
    date_to: date | None = None
    merchant_contains: str | None = Field(default=None, max_length=100)
    category_contains: str | None = Field(default=None, max_length=100)
    product_contains: str | None = Field(default=None, max_length=100)
    day_type: Literal["any", "weekend", "weekday"] = "any"
    limit: int = Field(default=10, ge=1, le=25)

    @model_validator(mode="after")
    def check(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        if self.source == "transactions" and (
            self.product_contains or self.group_by == "product"
        ):
            raise ValueError("Product filters and grouping require items")
        if self.action == "list" and self.group_by != "none":
            raise ValueError("Lists cannot use group_by")
        if self.action == "aggregate" and self.group_by == "weekday" and self.day_type != "any":
            raise ValueError("Use either weekday grouping or a day filter")
        return self


class FinancePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[FinanceQuery] = Field(min_length=1, max_length=3)


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=700)
