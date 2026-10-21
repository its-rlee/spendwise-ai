
from uuid import uuid4

from .models import TransactionDraft
from .extraction_schemas import (
    ReceiptExtraction,
    StatementExtraction,
)


def make_transaction_drafts(
    document_id: str,
    result: ReceiptExtraction | StatementExtraction,
    user_id: str,
) -> list[TransactionDraft]:

    drafts = []

    if isinstance(result, ReceiptExtraction):
        reasons = list(result.review_reasons)

        if not result.merchant:
            reasons.append("Merchant requires review")

        if result.total is None or result.total <= 0:
            reasons.append("Valid total is missing")

        if result.purchase_date is None:
            reasons.append("Date requires review")

        if result.currency is None:
            reasons.append("Currency requires review")

        if result.needs_review and not reasons:
            reasons.append("AI flagged this receipt")

        drafts.append(
            TransactionDraft(
                id=str(uuid4()),
                document_id=document_id,
                user_id=user_id,
                source_index=0,
                merchant=result.merchant,
                amount=result.total,
                direction="debit",
                transaction_date=result.purchase_date,
                currency=result.currency,
                review_reasons=list(dict.fromkeys(reasons)),
                status="pending",
                receipt_items=[
                    {
                        "source_line_index": index,
                        "raw_description": item.raw_description,
                        "store_item_code": item.store_item_code,
                        "name": item.name,
                        "amount": (
                            str(item.price)
                            if item.price is not None
                            else None
                        ),
                        "category": item.category or "Uncategorized",
                    }
                    for index, item in enumerate(result.items)
                ],
                receipt_subtotal=result.subtotal,
                items_reviewed=False,
            )
        )

    elif isinstance(result, StatementExtraction):
        for index, row in enumerate(result.transactions):
            reasons = list(result.review_reasons)

            if not row.description:
                reasons.append("Description is missing")

            if row.posted_date is None:
                reasons.append("Date requires review")

            if row.amount is None or row.amount <= 0:
                reasons.append("Valid amount is missing")

            if row.direction == "unknown":
                reasons.append("Direction requires review")

            # Currency isn't included in our
            # current statement extraction schema.
            reasons.append("Currency requires review")

            if result.needs_review and not result.review_reasons:
                reasons.append("AI flagged this statement")

            drafts.append(
                TransactionDraft(
                    id=str(uuid4()),
                    document_id=document_id,
                    user_id=user_id,
                    source_index=index,
                    merchant=row.description,
                    amount=row.amount,
                    direction=(
                        row.direction
                        if row.direction != "unknown"
                        else None
                    ),
                    transaction_date=row.posted_date,
                    currency=None,
                    review_reasons=list(
                        dict.fromkeys(reasons)
                    ),
                    status="pending",
                )
            )

    else:
        raise ValueError(
            "Unsupported extraction result"
        )

    return drafts
