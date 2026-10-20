
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Document,
    Transaction,
    TransactionDraft,
)


def get_owned_document(
    db: Session,
    document_id: str,
    user_id: str,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document


def get_owned_transaction(
    db: Session,
    transaction_id: int,
    user_id: str,
) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )

    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found",
        )

    return transaction


def get_owned_draft(
    db: Session,
    draft_id: str,
    user_id: str,
) -> TransactionDraft:
    draft = db.scalar(
        select(TransactionDraft)
        .join(
            Document,
            TransactionDraft.document_id == Document.id,
        )
        .where(
            TransactionDraft.id == draft_id,
            TransactionDraft.user_id == user_id,
            Document.user_id == user_id,
        )
        .with_for_update()
    )

    if draft is None:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    return draft
