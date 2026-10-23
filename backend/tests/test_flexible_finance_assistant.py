"""Offline regression tests for Gemini-planned SQLAlchemy queries and isolation."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.assistant_planner import get_query_planner
from app.auth import AuthUser, get_current_user
from app.database import Base, get_db
from app.finance_analytics import get_utc_today
from app.finance_planner import GeminiFinancePlanner
from app.finance_query_schemas import FinancePlan, FinanceQuery
from app.main import app
from app.models import Transaction, TransactionItem


class FakeGeminiPlanner(GeminiFinancePlanner):
    def __init__(self, queries):
        self.queries = queries
        self.last_history = None

    def plan(self, question, history=None, today=None):
        self.last_history = history
        return FinancePlan(queries=self.queries)


@pytest.fixture
def finance_client():
    raw_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine = raw_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )
    Base.metadata.create_all(engine)
    alice, bob = str(uuid4()), str(uuid4())

    with Session(engine) as db:
        records = [
            (alice, "Costco", "Mixed Shopping", "196.70", "debit", date(2023, 10, 26)),
            (alice, "Target", "Shopping", "20.00", "debit", date(2026, 10, 20)),
            (alice, "Payroll", "Income", "300.00", "credit", date(2026, 10, 21)),
            (bob, "Private Costco", "Shopping", "999.00", "debit", date(2026, 10, 22)),
        ]
        made = []
        for owner, merchant, category, amount, direction, day in records:
            row = Transaction(
                user_id=owner, merchant=merchant, category=category,
                amount=Decimal(amount), direction=direction,
                currency="USD", transaction_date=day,
            )
            db.add(row)
            db.flush()
            made.append(row)
        db.add_all([
            TransactionItem(
                transaction_id=made[0].id, line_index=0,
                name="Kirkland Chicken", category="Meat",
                amount=Decimal("19.99"),
            ),
            TransactionItem(
                transaction_id=made[0].id, line_index=1,
                name="Tide Laundry Pods", category="Household",
                amount=Decimal("29.99"),
            ),
            TransactionItem(
                transaction_id=made[3].id, line_index=0,
                name="Private Chicken", category="Meat",
                amount=Decimal("777.00"),
            ),
        ])
        db.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    planner = FakeGeminiPlanner([])
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_query_planner] = lambda: planner
    app.dependency_overrides[get_utc_today] = lambda: date(2026, 10, 22)
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=alice)

    client = TestClient(app)
    try:
        yield client, planner, alice, bob
    finally:
        client.close()
        app.dependency_overrides.clear()
        raw_engine.dispose()


def ask(client, question="What did I spend?", history=None):
    return client.post(
        "/api/v1/assistant/ask",
        json={"question": question, "history": history or []},
    )


def test_most_recent_expense_from_approved_user_transactions(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = [
        FinanceQuery(
            source="transactions", action="list", sort="latest",
            direction="debit", limit=1,
        )
    ]
    response = ask(client, "What was my latest expense?")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["intent"] == "dynamic_finance_query"
    assert result["facts"]["queries"][0]["rows"][0]["merchant"] == "Target"
    assert result["facts"]["queries"][0]["rows"][0]["amount"] == "20.00"
    assert "999.00" not in response.text


def test_item_search_and_owner_isolation(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = [
        FinanceQuery(
            source="items", action="list", product_contains="chicken",
            sort="latest",
        )
    ]
    response = ask(client, "When did I buy chicken?")
    assert response.status_code == 200, response.text
    rows = response.json()["facts"]["queries"][0]["rows"]
    assert len(rows) == 1
    assert rows[0]["product"] == "Kirkland Chicken"
    assert rows[0]["merchant"] == "Costco"
    assert rows[0]["date"] == "2023-10-26"


def test_category_aggregate_does_not_include_other_user(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = [
        FinanceQuery(
            source="items", action="aggregate", measure="sum",
            group_by="category", sort="highest",
        )
    ]
    response = ask(client, "What product categories cost the most?")
    assert response.status_code == 200, response.text
    rows = response.json()["facts"]["queries"][0]["rows"]
    assert {row["group"]: row["value"] for row in rows} == {
        "Household": "29.99", "Meat": "19.99"
    }


def test_month_and_income_aggregation(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = [
        FinanceQuery(
            source="transactions", action="aggregate", measure="sum",
            group_by="month", sort="oldest", direction="debit",
        ),
        FinanceQuery(
            source="transactions", action="aggregate", measure="sum",
            group_by="none", direction="credit",
        ),
    ]
    response = ask(client, "Compare expenses and income")
    assert response.status_code == 200, response.text
    results = response.json()["facts"]["queries"]
    assert [row["group"] for row in results[0]["rows"]] == [
        "2023-10", "2026-10"
    ]
    assert [row["value"] for row in results[0]["rows"]] == [
        "196.70", "20.00"
    ]
    assert results[1]["rows"][0]["value"] == "300.00"


def test_followup_history_is_passed_but_never_as_user_scope(finance_client):
    client, planner, alice, _ = finance_client
    planner.queries = [
        FinanceQuery(
            source="transactions", action="aggregate",
            group_by="none", measure="sum",
        )
    ]
    history = [
        {"role": "user", "content": "How much did I spend?"},
        {"role": "assistant", "content": "Show approved transactions."},
    ]
    response = ask(client, "And overall spending?", history)
    assert response.status_code == 200, response.text
    assert len(planner.last_history) == 2
    assert response.json()["facts"]["queries"][0]["rows"][0]["value"] == "216.70"


def test_empty_plan_is_safe_and_not_a_server_error(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = []
    response = ask(client, "Predict the next stock price")
    assert response.status_code == 200, response.text
    assert response.json()["intent"] == "unavailable_data"
    assert response.json()["facts"]["queries"] == []


def test_reject_sql_fields_cross_domain_and_unbounded_plans():
    with pytest.raises(ValidationError):
        FinanceQuery.model_validate({
            "source": "transactions", "action": "list",
            "sql": "DELETE FROM spendwise.transactions",
        })
    with pytest.raises(ValidationError):
        FinanceQuery(source="transactions", action="list",
                     product_contains="chicken")
    with pytest.raises(ValidationError):
        FinanceQuery(source="items", action="list", limit=100000)
    with pytest.raises(ValidationError):
        FinancePlan(queries=[
            FinanceQuery(source="transactions", action="list")
            for _ in range(4)
        ])


def test_question_history_has_limits(finance_client):
    client, planner, _, _ = finance_client
    response = ask(
        client, "What did I buy?",
        [{"role": "assistant", "content": "x"} for _ in range(7)],
    )
    assert response.status_code == 422


def test_wildcards_in_product_names_are_not_sql_wildcards(finance_client):
    client, planner, _, _ = finance_client
    planner.queries = [
        FinanceQuery(source="items", action="list", product_contains="%")
    ]
    response = ask(client, "Find percent signs in product names")
    assert response.status_code == 200, response.text
    assert response.json()["facts"]["queries"][0]["rows"] == []
