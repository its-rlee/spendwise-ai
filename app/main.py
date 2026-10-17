
from decimal import Decimal
from datetime import date
from pydantic import field_validator

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="SpendWise AI",
    description="AI-powered financial intelligence API",
    version="0.1.0",
)


class TransactionInput(BaseModel):
    merchant: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    category: str = "Uncategorized"

    # Optional transaction date
    transaction_date: date | None = None

    # Default currency is USD
    currency: str = Field(
        default="USD",
        pattern=r"^[A-Z]{3}$"
    )
    
    # Reject empty or whitespace-only merchants
    @field_validator("merchant")
    @classmethod
    def validate_merchant(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Merchant cannot be empty")

        return value


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "spendwise-api"}


@app.post("/api/v1/transactions/preview")
def preview_transaction(transaction: TransactionInput):
    return {
        "merchant": transaction.merchant,
        "amount": str(transaction.amount),
        "category": transaction.category,
        "transaction_date": transaction.transaction_date,
        "currency": transaction.currency,
        "message": "Transaction validated successfully",
    }
