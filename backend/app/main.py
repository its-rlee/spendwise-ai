
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

from .documents import router as documents_router

from .receipts import router as receipts_router

from .extraction import router as extraction_router

from .review import router as review_router

from .auth import AuthUser, get_current_user

from .ownership import get_owned_transaction

from .assistant import router as assistant_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SpendWise AI",
    description="AI-powered financial intelligence API",
    version="0.1.0",
)

app.include_router(documents_router)

app.include_router(receipts_router)

app.include_router(extraction_router)

app.include_router(review_router)

app.include_router(assistant_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
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


@app.get(
    "/api/v1/transactions",
    response_model=list[TransactionRead],
)
def list_transactions(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
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
    user: AuthUser = Depends(get_current_user),
):
    transaction = get_owned_transaction(
        db,
        transaction_id,
        user.id,
    )

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
    user: AuthUser = Depends(get_current_user),
):
    transaction = get_owned_transaction(
        db,
        transaction_id,
        user.id,
    )

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
    user: AuthUser = Depends(get_current_user),
):
    transaction = get_owned_transaction(
        db,
        transaction_id,
        user.id,
    )
    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    db.delete(transaction)
    db.commit()

    return Response(status_code=204)


@app.get("/api/v1/me")
def get_my_profile(
    user: AuthUser = Depends(get_current_user),
):
    return {
        "user_id": user.id,
        "authenticated": True,
    }

@app.post(
    "/api/v1/transactions",
    response_model=TransactionRead,
    status_code=201,
)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    transaction = Transaction(
        **data.model_dump(),
        user_id=user.id,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction
