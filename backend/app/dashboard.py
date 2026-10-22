"""Owner-scoped, deterministic spending dashboard; no generative AI calls."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db
from .finance_analytics import get_utc_today
from .models import Document, Transaction, TransactionItem

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])
ZERO = Decimal("0.00")


def month_shift(first: date, offset: int) -> date:
    value = first.year * 12 + first.month - 1 + offset
    return date(value // 12, value % 12 + 1, 1)


def amount_text(value: Decimal | None) -> str:
    return f"{value or ZERO:.2f}"


class MonthRow(BaseModel):
    month: str
    expenses: str
    income: str


class CategoryRow(BaseModel):
    category: str
    amount: str


class ItemRow(BaseModel):
    name: str
    category: str
    amount: str


class PurchaseRow(BaseModel):
    id: int
    merchant: str
    amount: str
    currency: str
    category: str
    date: date | None
    direction: str
    items: list[ItemRow]


class PendingRow(BaseModel):
    id: str
    filename: str
    status: str


class DashboardResponse(BaseModel):
    currency: str
    available_currencies: list[str]
    month: str
    this_month_expenses: str
    this_month_income: str
    this_month_net: str
    last_month_expenses: str
    same_point_last_month_expenses: str
    monthly: list[MonthRow]
    item_categories: list[CategoryRow]
    top_items: list[ItemRow]
    recent_purchases: list[PurchaseRow]
    pending_receipts: list[PendingRow]
    pending_receipt_count: int
    insights: list[str]


@router.get("", response_model=DashboardResponse)
def dashboard(
    currency: str = Query(default="USD", pattern=r"^[A-Z]{3}$"),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
    today: date = Depends(get_utc_today),
):
    this_month = today.replace(day=1)
    next_month = month_shift(this_month, 1)
    last_month = month_shift(this_month, -1)
    six_months_ago = month_shift(this_month, -5)

    available = sorted(set(db.scalars(
        select(Transaction.currency)
        .where(Transaction.user_id == user.id)
        .distinct()
    ).all()))
    if currency not in available:
        available.append(currency)
        available.sort()

    # A single aggregate query handles the entire six-month trend.
    buckets = {
        month_shift(this_month, -i).strftime("%Y-%m"): {
            "debit": ZERO, "credit": ZERO,
        }
        for i in range(6)
    }
    rows = db.execute(
        select(
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
            Transaction.direction,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.currency == currency,
            Transaction.transaction_date >= six_months_ago,
            Transaction.transaction_date < next_month,
            Transaction.direction.in_(("debit", "credit")),
        )
        .group_by(
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
            Transaction.direction,
        )
    ).all()
    for year, month, direction, total in rows:
        key = f"{int(year):04d}-{int(month):02d}"
        if key in buckets and direction in buckets[key]:
            buckets[key][direction] = total or ZERO

    monthly = [
        MonthRow(
            month=key,
            expenses=amount_text(value["debit"]),
            income=amount_text(value["credit"]),
        )
        for key, value in sorted(buckets.items())
    ]
    current = buckets[this_month.strftime("%Y-%m")]
    previous = buckets[last_month.strftime("%Y-%m")]

    # Compare identical elapsed calendar days, not a partial month to
    # an entire previous month. Clamp for shorter months.
    previous_end = min(
        last_month + timedelta(days=today.day),
        this_month,
    )
    prior_same_point = db.scalar(
        select(func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user.id,
            Transaction.currency == currency,
            Transaction.direction == "debit",
            Transaction.transaction_date >= last_month,
            Transaction.transaction_date < previous_end,
        )
    ) or ZERO

    item_scope = (
        Transaction.user_id == user.id,
        Transaction.currency == currency,
        Transaction.direction == "debit",
        Transaction.transaction_date >= this_month,
        Transaction.transaction_date < next_month,
    )
    category_rows = db.execute(
        select(
            TransactionItem.category,
            func.sum(TransactionItem.amount).label("total"),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(*item_scope)
        .group_by(TransactionItem.category)
        .order_by(func.sum(TransactionItem.amount).desc())
        .limit(8)
    ).all()
    item_categories = [
        CategoryRow(category=category or "Uncategorized", amount=amount_text(total))
        for category, total in category_rows
    ]

    product_rows = db.execute(
        select(
            TransactionItem.name,
            TransactionItem.category,
            func.sum(TransactionItem.amount),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .where(*item_scope)
        .group_by(TransactionItem.name, TransactionItem.category)
        .order_by(func.sum(TransactionItem.amount).desc())
        .limit(6)
    ).all()
    top_items = [
        ItemRow(name=name, category=category, amount=amount_text(total))
        for name, category, total in product_rows
    ]

    # Show recent purchases in ALL currencies, with their actual currency,
    # even when the summary has been filtered to USD or another currency.
    purchases = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.transaction_date.desc().nullslast(),
                  Transaction.id.desc())
        .limit(15)
    ).all()

    ids = [p.id for p in purchases]
    items_by_transaction: dict[int, list[ItemRow]] = {i: [] for i in ids}
    if ids:
        for transaction_id, name, category, item_amount in db.execute(
            select(
                TransactionItem.transaction_id,
                TransactionItem.name,
                TransactionItem.category,
                TransactionItem.amount,
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user.id,
                TransactionItem.transaction_id.in_(ids),
            )
            .order_by(
                TransactionItem.transaction_id,
                TransactionItem.line_index,
            )
        ):
            items_by_transaction[transaction_id].append(
                ItemRow(
                    name=name,
                    category=category,
                    amount=amount_text(item_amount),
                )
            )

    recent = [
        PurchaseRow(
            id=p.id,
            merchant=p.merchant,
            amount=amount_text(p.amount),
            currency=p.currency,
            category=p.category,
            date=p.transaction_date,
            direction=p.direction,
            items=items_by_transaction[p.id],
        )
        for p in purchases
    ]

    pending_filter = (
        Document.user_id == user.id,
        Document.s3_key.like(f"receipts/{user.id}/%"),
        Document.status.in_(
            ("uploaded", "text_ready", "needs_review", "awaiting_review")
        ),
    )
    pending_count = db.scalar(
        select(func.count(Document.id)).where(*pending_filter)
    ) or 0
    pending = [
        PendingRow(id=record.id, filename=record.filename, status=record.status)
        for record in db.scalars(
            select(Document)
            .where(*pending_filter)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(10)
        )
    ]

    insights: list[str] = []
    if prior_same_point > ZERO:
        change = (current["debit"] - prior_same_point) / prior_same_point * 100
        if change >= 10:
            insights.append(
                f"Recorded spending is {change:.0f}% higher than the "
                "same point last month. Review recent large purchases."
            )
        elif change <= -10:
            insights.append(
                f"Recorded spending is {abs(change):.0f}% lower than "
                "the same point last month."
            )
    if item_categories:
        leader = item_categories[0]
        insights.append(
            f"{leader.category} has the highest recorded item-line amount "
            f"this month ({currency} {leader.amount}). Check these purchases "
            "for possible savings."
        )
    if pending_count:
        insights.append(
            f"{pending_count} receipt(s) still need processing or approval. "
            "They are not included in spending totals."
        )

    return DashboardResponse(
        currency=currency,
        available_currencies=available,
        month=this_month.strftime("%Y-%m"),
        this_month_expenses=amount_text(current["debit"]),
        this_month_income=amount_text(current["credit"]),
        this_month_net=amount_text(current["credit"] - current["debit"]),
        last_month_expenses=amount_text(previous["debit"]),
        same_point_last_month_expenses=amount_text(prior_same_point),
        monthly=monthly,
        item_categories=item_categories,
        top_items=top_items,
        recent_purchases=recent,
        pending_receipts=pending,
        pending_receipt_count=pending_count,
        insights=insights,
    )
