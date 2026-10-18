
from uuid import uuid4

from .models import TransactionDraft
from .extraction_schemas import (
    ReceiptExtraction,
    StatementExtraction,
)


def make_transaction_drafts(
    document_id: str,
    result: ReceiptExtraction | StatementExtraction,
) -> list[TransactionDraft]:

    drafts = []

    if isinstance(result, ReceiptExtraction):
        reasons = list(result.review_reasons)

        if not result.merchant:
            reasons.append("Merchant requires review")

        if not result.total or result.total <= 0:
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
                source_index=0,
                merchant=result.merchant,
                amount=result.total,
                direction="debit",
                transaction_date=result.purchase_date,
                currency=result.currency,
                review_reasons=list(dict.fromkeys(reasons)),
                status="pending",
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

            # The Day 5 statement schema does not
            # yet extract a currency field.
            reasons.append("Currency requires review")

            drafts.append(
                TransactionDraft(
                    id=str(uuid4()),
                    document_id=document_id,
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

    return drafts
