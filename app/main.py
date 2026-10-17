
from decimal import Decimal
from datetime import date
from pydantic import field_validator

from fastapi import FastAPI, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Transaction
from .schemas import (
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
)

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


@app.post(
    "/api/v1/transactions",
    response_model=TransactionRead,
    status_code=201,
)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
):
    transaction = Transaction(**data.model_dump())

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


@app.get(
    "/api/v1/transactions",
    response_model=list[TransactionRead],
)
def list_transactions(
    db: Session = Depends(get_db),
):
    statement = (
        select(Transaction)
        .order_by(Transaction.id)
        .limit(100)
    )

    return db.scalars(statement).all()


@app.get(
    "/api/v1/transactions/{transaction_id}",
    response_model=TransactionRead,
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    transaction = db.get(Transaction, transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return transaction


@app.patch(
    "/api/v1/transactions/{transaction_id}",
    response_model=TransactionRead,
)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
):
    transaction = db.get(Transaction, transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    transaction.category = data.category

    db.commit()
    db.refresh(transaction)

    return transaction


@app.delete(
    "/api/v1/transactions/{transaction_id}",
    status_code=204,
)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    transaction = db.get(Transaction, transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    db.delete(transaction)
    db.commit()

    return Response(status_code=204)

