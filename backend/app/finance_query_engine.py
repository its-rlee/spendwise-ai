"""Compile only allowlisted SQLAlchemy operations over the signed-in user's records.

No SQL text, table names, arbitrary column names, or user IDs from the LLM
ever reach the database query builder.
"""
from decimal import Decimal, InvalidOperation

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from .finance_query_schemas import FinanceQuery
from .models import Transaction, TransactionItem


WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday")


def money(value):
    try:
        return f"{Decimal(str(value or 0)):.2f}"
    except (InvalidOperation, ValueError):
        return "0.00"


def run_finance_query(db: Session, user_id: str, query: FinanceQuery) -> dict:
    transaction = Transaction
    is_item = query.source == "items"
    amount = TransactionItem.amount if is_item else transaction.amount

    filters = [
        transaction.user_id == user_id,
        transaction.currency == query.currency,
    ]
    if query.direction != "both":
        filters.append(transaction.direction == query.direction)
    if query.date_from:
        filters.append(transaction.transaction_date >= query.date_from)
    if query.date_to:
        filters.append(transaction.transaction_date <= query.date_to)
    if query.merchant_contains:
        filters.append(
            func.lower(transaction.merchant).contains(
                query.merchant_contains.lower(), autoescape=True
            )
        )
    if query.category_contains:
        category = TransactionItem.category if is_item else transaction.category
        filters.append(
            func.lower(category).contains(
                query.category_contains.lower(), autoescape=True
            )
        )
    if query.product_contains:
        filters.append(
            func.lower(TransactionItem.name).contains(
                query.product_contains.lower(), autoescape=True
            )
        )
    if query.day_type != "any":
        day_of_week = extract("dow", transaction.transaction_date)
        filters.append(
            day_of_week.in_((0, 6))
            if query.day_type == "weekend"
            else day_of_week.in_((1, 2, 3, 4, 5))
        )

    def joined(statement):
        if is_item:
            return statement.join(
                transaction, TransactionItem.transaction_id == transaction.id
            )
        return statement

    if query.action == "list":
        columns = [
            transaction.id, transaction.merchant,
            transaction.transaction_date, transaction.category,
            amount, transaction.currency, transaction.direction,
        ]
        if is_item:
            columns.extend([
                TransactionItem.name,
                TransactionItem.category,
                TransactionItem.line_index,
            ])
        statement = joined(select(*columns)).where(*filters)
        label = TransactionItem.name if is_item else transaction.merchant
        tie_break = [
            transaction.transaction_date.desc().nullslast(),
            transaction.id.desc(),
        ]
        if is_item:
            tie_break.append(TransactionItem.line_index.desc())

        if query.sort == "oldest":
            ordering = [
                transaction.transaction_date.asc().nullsfirst(),
                transaction.id.asc(),
            ]
        elif query.sort == "highest":
            ordering = [amount.desc(), *tie_break]
        elif query.sort == "lowest":
            ordering = [amount.asc(), *tie_break]
        elif query.sort == "alphabetical":
            ordering = [label.asc(), *tie_break]
        else:
            ordering = tie_break

        result = db.execute(
            statement.order_by(*ordering).limit(query.limit)
        ).all()
        rows = []
        for row in result:
            identifier, merchant, day, category, value, currency, direction = row[:7]
            entry = {
                "transaction_id": identifier,
                "merchant": merchant,
                "date": day.isoformat() if day else None,
                "transaction_category": category,
                "amount": money(value),
                "currency": currency,
                "direction": direction,
            }
            if is_item:
                entry.update({
                    "product": row[7],
                    "category": row[8],
                    "line_index": row[9],
                })
            rows.append(entry)

    else:
        aggregate = {
            "sum": func.sum(amount),
            "count": func.count(TransactionItem.id if is_item else transaction.id),
            "average": func.avg(amount),
            "minimum": func.min(amount),
            "maximum": func.max(amount),
        }[query.measure]
        group = query.group_by
        keys = []
        if group == "merchant":
            keys = [transaction.merchant]
        elif group == "category":
            keys = [TransactionItem.category if is_item else transaction.category]
        elif group == "product":
            keys = [TransactionItem.name]
        elif group == "month":
            keys = [
                extract("year", transaction.transaction_date),
                extract("month", transaction.transaction_date),
            ]
            filters.append(transaction.transaction_date.is_not(None))
        elif group == "weekday":
            keys = [extract("dow", transaction.transaction_date)]
            filters.append(transaction.transaction_date.is_not(None))

        statement = joined(
            select(*keys, aggregate, func.count(
                TransactionItem.id if is_item else transaction.id
            ))
        ).where(*filters)

        if keys:
            statement = statement.group_by(*keys)
            if query.sort == "lowest":
                statement = statement.order_by(aggregate.asc())
            elif query.sort == "alphabetical":
                statement = statement.order_by(*[key.asc() for key in keys])
            elif query.sort == "latest" and group == "month":
                statement = statement.order_by(keys[0].desc(), keys[1].desc())
            elif query.sort == "oldest" and group == "month":
                statement = statement.order_by(keys[0].asc(), keys[1].asc())
            else:
                statement = statement.order_by(aggregate.desc())
        statement = statement.limit(query.limit)
        result = db.execute(statement).all()
        rows = []
        for row in result:
            key_values = row[:len(keys)]
            value, count = row[len(keys):]
            entry = {
                "value": str(int(value or 0)) if query.measure == "count" else money(value),
                "record_count": int(count),
            }
            if group == "month":
                entry["group"] = f"{int(key_values[0]):04d}-{int(key_values[1]):02d}"
            elif group == "weekday":
                entry["group"] = WEEKDAYS[int(key_values[0])]
            elif keys:
                entry["group"] = key_values[0] or "Uncategorized"
            rows.append(entry)

    return {
        "source": query.source,
        "action": query.action,
        "measure": query.measure if query.action == "aggregate" else None,
        "group_by": query.group_by,
        "currency": query.currency,
        "date_from": query.date_from.isoformat() if query.date_from else None,
        "date_to": query.date_to.isoformat() if query.date_to else None,
        "rows": rows,
        "note": (
            "Item amounts are receipt line amounts, not verified unit prices; "
            "their sum may differ from receipt totals due to taxes, discounts, "
            "quantities or extraction errors."
            if is_item else
            "Amounts come from approved transactions; income and expenses "
            "must not be added together without considering direction."
        ),
    }


def describe_results(results: list[dict]) -> str:
    parts = []
    for result in results:
        rows = result["rows"]
        source = "receipt item lines" if result["source"] == "items" else "transactions"
        currency = result["currency"]
        if not rows:
            parts.append(
                f"No matching approved {source} were found. "
                "Try a different date, product, merchant or category."
            )
            continue

        if result["action"] == "list":
            values = []
            for row in rows[:8]:
                name = row.get("product") or row["merchant"]
                date_text = f", {row['date']}" if row["date"] else ""
                merchant = f" at {row['merchant']}" if row.get("product") else ""
                values.append(
                    f"{name}{merchant} ({currency} {row['amount']}{date_text})"
                )
            parts.append(
                f"Matching approved {source}: " + "; ".join(values)
                + ("; more results are in the details." if len(rows) > 8 else ".")
            )
        else:
            measure = result["measure"]
            group = result["group_by"]
            if group == "none":
                value = rows[0]["value"]
                unit = "records" if measure == "count" else currency
                parts.append(
                    f"Across {rows[0]['record_count']} approved {source}, "
                    f"{measure} = {value} {unit}."
                )
            else:
                values = [
                    f"{row['group']}: {row['value']}"
                    for row in rows[:8]
                ]
                suffix = " records" if measure == "count" else f" {currency}"
                parts.append(
                    f"Approved {source}, {measure} by {group}: "
                    + "; ".join(values) + suffix + "."
                )
    return "\n\n".join(parts)
