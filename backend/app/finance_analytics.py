
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .assistant_schemas import QueryPlan
from .models import Transaction


ZERO = Decimal("0.00")


def get_utc_today() -> date:
    return datetime.now(timezone.utc).date()


def month_boundaries(period: str, today: date):
    first = today.replace(day=1)

    if period == "this_month":
        if first.month == 12:
            end = date(first.year + 1, 1, 1)
        else:
            end = date(
                first.year,
                first.month + 1,
                1,
            )

        return first, end

    if period == "last_month":
        previous_day = first - timedelta(days=1)
        start = previous_day.replace(day=1)
        return start, first

    return None, None


def calculate_report(
    db: Session,
    user_id: str,
    plan: QueryPlan,
    today: date,
):
    start, end = month_boundaries(
        plan.period,
        today,
    )

    # Apply these filters to EVERY query.
    filters = [
        Transaction.user_id == user_id,
        Transaction.currency == "USD",
    ]

    if start is not None:
        filters.append(
            Transaction.transaction_date >= start
        )

    if end is not None:
        filters.append(
            Transaction.transaction_date < end
        )

    period_label = plan.period.replace("_", " ")

    if plan.intent in (
        "category_total",
        "merchant_total",
    ):
        filters.append(
            Transaction.direction == "debit"
        )

        if plan.intent == "category_total":
            target = plan.category.strip()

            filters.append(
                func.lower(Transaction.category)
                == target.lower()
            )
            description = f"category {target}"

        else:
            target = plan.merchant.strip()

            filters.append(
                func.lower(Transaction.merchant)
                == target.lower()
            )
            description = f"merchant {target}"

        total = db.scalar(
            select(func.sum(Transaction.amount))
            .where(*filters)
        ) or ZERO

        count = db.scalar(
            select(func.count(Transaction.id))
            .where(*filters)
        ) or 0

        facts = {
            "currency": "USD",
            "total": f"{total:.2f}",
            "transaction_count": count,
        }

        if count == 0:
            answer = (
                f"No matching approved USD expenses "
                f"found for {description} "
                f"during {period_label}."
            )
        else:
            answer = (
                f"You spent ${total:,.2f} USD "
                f"at {description} during {period_label}, "
                f"across {count} transaction(s)."
            )

        return answer, facts

    if plan.intent == "largest_expenses":
        filters.append(
            Transaction.direction == "debit"
        )

        statement = (
            select(Transaction)
            .where(*filters)
            .order_by(
                Transaction.amount.desc(),
                Transaction.id.asc(),
            )
            .limit(plan.limit)
        )

        transactions = db.scalars(statement).all()

        rows = [
            {
                "merchant": transaction.merchant,
                "amount": f"{transaction.amount:.2f}",
                "date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
            }
            for transaction in transactions
        ]

        if not rows:
            answer = (
                "No approved USD expenses found "
                f"during {period_label}."
            )
        else:
            summary = "; ".join(
                f"{row['merchant']}: "
                f"${Decimal(row['amount']):,.2f}"
                for row in rows
            )

            answer = (
                f"Largest USD expenses during "
                f"{period_label}: {summary}."
            )

        return answer, {
            "currency": "USD",
            "transactions": rows,
        }

    if plan.intent == "cash_flow":
        statement = (
            select(
                Transaction.direction,
                func.sum(Transaction.amount),
            )
            .where(*filters)
            .group_by(Transaction.direction)
        )

        totals = {
            direction: amount
            for direction, amount in db.execute(statement)
        }

        income = totals.get("credit", ZERO)
        expenses = totals.get("debit", ZERO)
        net = income - expenses

        answer = (
            f"During {period_label}, "
            f"you received ${income:,.2f} USD "
            f"and spent ${expenses:,.2f} USD. "
            f"Your net cash flow was "
            f"${net:,.2f} USD."
        )

        return answer, {
            "currency": "USD",
            "income": f"{income:.2f}",
            "expenses": f"{expenses:.2f}",
            "net_cash_flow": f"{net:.2f}",
        }

    raise ValueError("Unsupported query intent")
