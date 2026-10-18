
from .extraction_schemas import (
    ReceiptExtraction,
    StatementExtraction,
)


def review_receipt(
    result: ReceiptExtraction,
) -> ReceiptExtraction:
    reasons = list(result.review_reasons)

    if not result.merchant:
        reasons.append("Merchant is missing")

    if result.purchase_date is None:
        reasons.append("Purchase date is missing")

    if result.total is None:
        reasons.append("Receipt total is missing")

    if result.currency is None:
        reasons.append("Currency is unverified")

    if (
        result.subtotal is not None
        and result.tax is not None
        and result.total is not None
    ):
        calculated = result.subtotal + result.tax

        if abs(calculated - result.total) > 0.01:
            reasons.append(
                "Subtotal + tax does not match total"
            )

    reasons = list(dict.fromkeys(reasons))

    return result.model_copy(
        update={
            "needs_review": bool(reasons)
            or result.needs_review,
            "review_reasons": reasons,
        }
    )


def review_statement(
    result: StatementExtraction,
) -> StatementExtraction:
    reasons = list(result.review_reasons)

    if not result.transactions:
        reasons.append("No transactions extracted")

    for index, transaction in enumerate(
        result.transactions,
        start=1,
    ):
        if (
            transaction.posted_date is None
            or transaction.description is None
            or transaction.amount is None
            or transaction.direction == "unknown"
        ):
            reasons.append(
                f"Transaction {index} is incomplete"
            )

    reasons = list(dict.fromkeys(reasons))

    return result.model_copy(
        update={
            "needs_review": bool(reasons)
            or result.needs_review,
            "review_reasons": reasons,
        }
    )
