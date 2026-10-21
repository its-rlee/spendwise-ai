from decimal import Decimal
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Transaction,
    TransactionDraft,
    TransactionItem,
)
from .review_schemas import (
    DraftRead,
    TransactionApproval,
    DraftRejection,
    ReceiptItemsUpdate,
    ReceiptItemEdit,
)
from .review_service import make_transaction_drafts
from .extraction import run_document_extraction
from .s3_service import get_s3_client
from .ocr_service import get_ocr_reader
from .llm_service import get_extractor

from .auth import AuthUser, get_current_user
from .ownership import (
    get_owned_document,
    get_owned_draft,
)


router = APIRouter(tags=["Transaction Review"])


# --------------------------------------------------
# 1. PREPARE DOCUMENT FOR REVIEW
# --------------------------------------------------

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
    user: AuthUser = Depends(get_current_user),
):
    # Verify document ownership.
    # Raises 404 if missing or owned by another user.
    document = get_owned_document(
        db,
        document_id,
        user.id,
    )

    existing = db.scalar(
        select(TransactionDraft.id)
        .where(
            TransactionDraft.document_id == document_id,
            TransactionDraft.user_id == user.id,
        )
        .limit(1)
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Document already prepared for review",
        )

    # Reuse Day 5 extraction with ownership validation.
    result = run_document_extraction(
        document_id=document_id,
        db=db,
        s3=s3,
        ocr_reader=ocr_reader,
        extractor=extractor,
        user_id=user.id,
    )

    # Assign owner to every new draft.
    drafts = make_transaction_drafts(
        document_id,
        result,
        user.id,
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


# --------------------------------------------------
# 2. LIST USER'S DOCUMENT DRAFTS
# --------------------------------------------------

@router.get(
    "/api/v1/documents/{document_id}/drafts",
    response_model=list[DraftRead],
)
def list_document_drafts(
    document_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    # Check ownership before querying drafts.
    get_owned_document(
        db,
        document_id,
        user.id,
    )

    statement = (
        select(TransactionDraft)
        .where(
            TransactionDraft.document_id == document_id,
            TransactionDraft.user_id == user.id,
        )
        .order_by(TransactionDraft.source_index)
    )

    return db.scalars(statement).all()


# --------------------------------------------------
# 3. APPROVE TRANSACTION DRAFT
# --------------------------------------------------

@router.post(
    "/api/v1/drafts/{draft_id}/approve",
    status_code=201,
)
def approve_draft(
    draft_id: str,
    data: TransactionApproval,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    # Ownership check + PostgreSQL row lock.
    draft = get_owned_draft(
        db,
        draft_id,
        user.id,
    )

    if draft.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Draft has already been processed",
        )

    # Detect possible duplicates belonging ONLY
    # to the currently authenticated user.
    similar_id = db.scalar(
        select(Transaction.id)
        .where(
            Transaction.user_id == user.id,
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
        # Release the row lock before returning 409.
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail={
                "message": "Possible duplicate transaction",
                "existing_transaction_id": similar_id,
                "instruction": (
                    "Review the existing transaction. "
                    "Set confirm_similar=true only if "
                    "this is a separate real transaction."
                ),
            },
        )

    document = get_owned_document(
        db,
        draft.document_id,
        user.id,
    )

    if (
        document.s3_key.startswith("receipts/")
        and not draft.items_reviewed
    ):
        raise HTTPException(
            status_code=409,
            detail="Review receipt items before approval",
        )

    # Validate approved item data, not just the
    # AI-generated draft structure.
    items = [
        ReceiptItemEdit.model_validate(item)
        for item in (draft.receipt_items or [])
    ]

    if any(item.amount is None for item in items):
        raise HTTPException(
            status_code=422,
            detail="Every approved item needs an amount",
        )

    # A subtotal check is helpful but is not always
    # decisive: receipts can include discounts or fees.
    if items and draft.receipt_subtotal is not None:
        item_sum = sum(
            (item.amount for item in items),
            Decimal("0.00"),
        )

        if (
            abs(item_sum - draft.receipt_subtotal)
            > Decimal("0.01")
            and not data.confirm_item_mismatch
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Receipt item subtotal mismatch",
                    "item_sum": str(item_sum),
                    "receipt_subtotal": str(
                        draft.receipt_subtotal
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
        user_id=user.id,
    )

    try:
        db.add(transaction)
        db.flush()


        for index, item in enumerate(items):
            db.add(
                TransactionItem(
                    transaction_id=transaction.id,
                    line_index=index,
                    name=item.name,
                    category=item.category,
                    amount=item.amount,
                    raw_description=item.raw_description,
                    store_item_code=item.store_item_code,
                    source_line_index=item.source_line_index,
                )
            )

        draft.status = "approved"
        draft.approved_transaction_id = transaction.id

        db.flush()

        # Count ONLY pending drafts.
        pending_count = db.scalar(
            select(func.count(TransactionDraft.id))
            .where(
                TransactionDraft.document_id
                == draft.document_id,
                TransactionDraft.user_id == user.id,
                TransactionDraft.status == "pending",
            )
        )

        if pending_count == 0:
            document = get_owned_document(
                db,
                draft.document_id,
                user.id,
            )
            document.status = "processed"

        transaction_id = transaction.id

        # Save transaction, draft and document
        # status atomically.
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
        "transaction_id": transaction_id,
        "draft_id": draft_id,
        "status": "approved",
    }


# --------------------------------------------------
# 4. REJECT TRANSACTION DRAFT
# --------------------------------------------------

@router.post(
    "/api/v1/drafts/{draft_id}/reject",
)
def reject_draft(
    draft_id: str,
    data: DraftRejection,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    # Only the owner can reject their draft.
    draft = get_owned_draft(
        db,
        draft_id,
        user.id,
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

        pending_count = db.scalar(
            select(func.count(TransactionDraft.id))
            .where(
                TransactionDraft.document_id
                == draft.document_id,
                TransactionDraft.user_id == user.id,
                TransactionDraft.status == "pending",
            )
        )

        if pending_count == 0:
            document = get_owned_document(
                db,
                draft.document_id,
                user.id,
            )
            document.status = "processed"

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


@router.patch(
    "/api/v1/drafts/{draft_id}/items",
    response_model=DraftRead,
)
def update_draft_items(
    draft_id: str,
    payload: ReceiptItemsUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    draft = get_owned_draft(
        db,
        draft_id,
        user.id,
    )

    if draft.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Draft is no longer editable",
        )

    document = get_owned_document(
        db,
        draft.document_id,
        user.id,
    )

    if not document.s3_key.startswith("receipts/"):
        raise HTTPException(
            status_code=422,
            detail="Item editing is for receipts only",
        )

    # Replace the whole JSON list so SQLAlchemy
    # reliably detects the change.

    # Find original extracted items by stable source ID.
    original_items = {
        row["source_line_index"]: row
        for row in (draft.receipt_items or [])
        if row.get("source_line_index") is not None
    }

    seen = set()
    reviewed_items = []

    for item in payload.items:
        source_index = item.source_line_index

        if source_index is not None:
            if (
                source_index not in original_items
                or source_index in seen
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Invalid or duplicate source item",
                )

            seen.add(source_index)
            original = original_items[source_index]
        else:
            # This is a manually added item.
            original = {}

        reviewed_items.append({
            "source_line_index": source_index,
            "raw_description": original.get(
                "raw_description"
            ),
            "store_item_code": original.get(
                "store_item_code"
            ),
            "name": item.name,
            "amount": (
                str(item.amount)
                if item.amount is not None
                else None
            ),
            "category": item.category,
        })

    draft.receipt_items = reviewed_items
    draft.items_reviewed = True

    try:
        db.commit()
        db.refresh(draft)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Could not save receipt items",
        ) from exc

    return draft
