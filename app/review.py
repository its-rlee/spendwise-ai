
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Document, Transaction, TransactionDraft
from .review_schemas import DraftRead, TransactionApproval, DraftRejection
from .review_service import make_transaction_drafts
from .extraction import run_document_extraction
from .s3_service import get_s3_client
from .ocr_service import get_ocr_reader
from .llm_service import get_extractor


router = APIRouter(tags=["Transaction Review"])


@router.post(
    "/api/v1/documents/{document_id}/prepare",
    response_model=list[DraftRead],
    status_code=201,
)
def prepare_document(
    document_id: str,
    db: Session = Depends(get_db),
    s3=Depends(get_s3_client),
    ocr_reader=Depends(get_ocr_reader),
    extractor=Depends(get_extractor),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    existing = db.scalar(
        select(TransactionDraft.id)
        .where(TransactionDraft.document_id == document_id)
        .limit(1)
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Document already prepared for review",
        )

    result = run_document_extraction(
        document_id=document_id,
        db=db,
        s3=s3,
        ocr_reader=ocr_reader,
        extractor=extractor,
    )

    drafts = make_transaction_drafts(
        document_id,
        result,
    )

    if not drafts:
        raise HTTPException(
            status_code=422,
            detail="No financial transactions extracted",
        )

    if len(drafts) > 200:
        raise HTTPException(
            status_code=422,
            detail="Too many extracted transactions",
        )

    try:
        db.add_all(drafts)
        document.status = "awaiting_review"
        db.commit()

        for draft in drafts:
            db.refresh(draft)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Document drafts already exist",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not save transaction drafts",
        ) from exc

    return drafts


@router.get(
    "/api/v1/documents/{document_id}/drafts",
    response_model=list[DraftRead],
)
def list_document_drafts(
    document_id: str,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    statement = (
        select(TransactionDraft)
        .where(
            TransactionDraft.document_id == document_id
        )
        .order_by(TransactionDraft.source_index)
    )

    return db.scalars(statement).all()


@router.post(
    "/api/v1/drafts/{draft_id}/approve",
    status_code=201,
)
def approve_draft(
    draft_id: str,
    data: TransactionApproval,
    db: Session = Depends(get_db),
):
    # Lock the draft while approving it.
    draft = db.scalar(
        select(TransactionDraft)
        .where(TransactionDraft.id == draft_id)
        .with_for_update()
    )

    if draft is None:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    if draft.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Draft has already been processed",
        )

    # Similar transactions are warnings, not
    # automatically confirmed duplicates.
    similar_id = db.scalar(
        select(Transaction.id)
        .where(
            func.lower(Transaction.merchant)
            == data.merchant.lower(),
            Transaction.amount == data.amount,
            Transaction.transaction_date
            == data.transaction_date,
            Transaction.currency == data.currency,
            Transaction.direction == data.direction,
        )
        .limit(1)
    )

    if (
        similar_id is not None
        and not data.confirm_similar
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Possible duplicate transaction",
                "existing_transaction_id": similar_id,
                "instruction": (
                    "Review the existing record. "
                    "Use confirm_similar=true only if "
                    "this is a separate real transaction."
                ),
            },
        )

    transaction = Transaction(
        merchant=data.merchant,
        amount=data.amount,
        category=data.category,
        transaction_date=data.transaction_date,
        currency=data.currency,
        direction=data.direction,
        source_document_id=draft.document_id,
        source_index=draft.source_index,
    )

    try:
        db.add(transaction)
        db.flush()

        draft.status = "approved"
        draft.approved_transaction_id = transaction.id

        db.flush()

        remaining = db.scalar(
            select(func.count(TransactionDraft.id))
            .where(
                TransactionDraft.document_id
                == draft.document_id,
                TransactionDraft.status != "pending",
            )
        )

        if remaining == 0:
            document = db.get(
                Document,
                draft.document_id,
            )
            document.status = "processed"

        # Commit transaction and draft status together.
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Transaction was already saved",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not approve transaction",
        ) from exc

    return {
        "transaction_id": transaction.id,
        "draft_id": draft.id,
        "status": "approved",
    }


@router.post("/api/v1/drafts/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    data: DraftRejection,
    db: Session = Depends(get_db),
):
    draft = db.scalar(
        select(TransactionDraft)
        .where(TransactionDraft.id == draft_id)
        .with_for_update()
    )

    if draft is None:
        raise HTTPException(
            status_code=404,
            detail="Draft not found",
        )

    if draft.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Draft has already been processed",
        )

    draft.status = "rejected"
    draft.review_reasons = [
        *draft.review_reasons,
        f"Rejected by reviewer: {data.reason}",
    ]

    try:
        db.flush()

        pending = db.scalar(
            select(func.count(TransactionDraft.id))
            .where(
                TransactionDraft.document_id
                == draft.document_id,
                TransactionDraft.status == "pending",
            )
        )

        if pending == 0:
            db.get(
                Document,
                draft.document_id,
            ).status = "processed"

        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not reject draft",
        ) from exc

    return {
        "draft_id": draft_id,
        "status": "rejected",
    }

