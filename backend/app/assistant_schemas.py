
from typing import Any, Literal

from .finance_query_schemas import ChatTurn

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AssistantQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=8,
        max_length=300,
    )
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)

    @field_validator("question")
    @classmethod
    def check_question(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 8:
            raise ValueError("Question is too short")

        return value


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "category_total",
        "merchant_total",
        "largest_expenses",
        "cash_flow",
        "unsupported",
        "purchased_items",
        "top_item_categories",
    ]

    period: Literal[
        "this_month",
        "last_month",
        "all_time",
    ] = "this_month"

    category: str | None = Field(
        default=None,
        max_length=100,
    )

    merchant: str | None = Field(
        default=None,
        max_length=255,
    )

    limit: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def check_required_filters(self):
        if self.intent == "category_total":
            if not self.category or not self.category.strip():
                raise ValueError("Category is required")

        if self.intent in ("merchant_total", "purchased_items"):
            if not self.merchant or not self.merchant.strip():
                raise ValueError("Merchant is required")

        return self


class AssistantAnswer(BaseModel):
    question: str
    intent: str
    period: str
    answer: str
    facts: dict[str, Any]
