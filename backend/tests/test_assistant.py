
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import AuthUser, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Transaction

from app.assistant_planner import get_query_planner
from app.assistant_schemas import QueryPlan
from app.finance_analytics import get_utc_today


class FakePlanner:
    def plan(self, question):
        text = question.lower()

        if "grocer" in text:
            return QueryPlan(
                intent="category_total",
                category="Groceries",
                period=(
                    "last_month"
                    if "last month" in text
                    else "this_month"
                ),
            )

        if "cash flow" in text:
            return QueryPlan(
                intent="cash_flow",
                period="this_month",
            )

        if "largest" in text:
            return QueryPlan(
                intent="largest_expenses",
                period="this_month",
                limit=2,
            )

        return QueryPlan(intent="unsupported")


@pytest.fixture
def assistant_client():
    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    engine = sqlite_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=engine)

    alice = str(uuid4())
    bob = str(uuid4())

    records = [
        # Alice: current month expenses
        (alice, "Walmart", "Groceries",
         "20.00", "debit", date(2026, 10, 7)),

        (alice, "Costco", "Groceries",
         "10.50", "debit", date(2026, 10, 8)),

        # Alice: income
        (alice, "Payroll", "Income",
         "300.00", "credit", date(2026, 10, 10)),

        # Alice: previous month
        (alice, "Old Grocery", "Groceries",
         "5.00", "debit", date(2026, 9, 25)),

        # Bob: must not appear in Alice's results
        (bob, "Private Store", "Groceries",
         "999.00", "debit", date(2026, 10, 9)),
    ]

    with Session(engine) as db:
        for user_id, merchant, category, amount, direction, day in records:
            db.add(
                Transaction(
                    user_id=user_id,
                    merchant=merchant,
                    category=category,
                    amount=Decimal(amount),
                    direction=direction,
                    currency="USD",
                    transaction_date=day,
                )
            )

        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_query_planner] = (
        lambda: FakePlanner()
    )
    app.dependency_overrides[get_utc_today] = (
        lambda: date(2026, 10, 19)
    )

    client = TestClient(app)

    try:
        yield client, alice, bob
    finally:
        client.close()
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def as_user(user_id):
    app.dependency_overrides[get_current_user] = (
        lambda: AuthUser(id=user_id)
    )


def ask(client, question):
    return client.post(
        "/api/v1/assistant/ask",
        json={"question": question},
    )


def test_authentication_required(assistant_client):
    client, _, _ = assistant_client

    response = ask(
        client,
        "How much did I spend on groceries?",
    )

    assert response.status_code == 401


def test_grocery_total(assistant_client):
    client, alice, _ = assistant_client
    as_user(alice)

    response = ask(
        client,
        "Groceries this month total?",
    )

    assert response.status_code == 200

    facts = response.json()["facts"]

    assert facts["total"] == "30.50"
    assert facts["transaction_count"] == 2


def test_last_month_filter(assistant_client):
    client, alice, _ = assistant_client
    as_user(alice)

    response = ask(
        client,
        "Groceries last month total?",
    )

    assert response.status_code == 200
    assert response.json()["facts"]["total"] == "5.00"


def test_cash_flow(assistant_client):
    client, alice, _ = assistant_client
    as_user(alice)

    response = ask(
        client,
        "What is my cash flow this month?",
    )

    facts = response.json()["facts"]

    assert response.status_code == 200
    assert facts["income"] == "300.00"
    assert facts["expenses"] == "30.50"
    assert facts["net_cash_flow"] == "269.50"


def test_user_data_isolation(assistant_client):
    client, alice, bob = assistant_client

    as_user(alice)
    alice_response = ask(
        client,
        "Groceries this month total?",
    )

    as_user(bob)
    bob_response = ask(
        client,
        "Groceries this month total?",
    )

    assert alice_response.json()["facts"]["total"] == "30.50"
    assert bob_response.json()["facts"]["total"] == "999.00"


def test_unsupported_question(assistant_client):
    client, alice, _ = assistant_client
    as_user(alice)

    response = ask(
        client,
        "Predict tomorrow's stock market",
    )

    assert response.status_code == 422


def test_largest_expenses(assistant_client):
    client, alice, _ = assistant_client
    as_user(alice)

    response = ask(
        client,
        "Show my largest expenses this month",
    )

    assert response.status_code == 200

    rows = response.json()["facts"]["transactions"]

    assert len(rows) == 2
    assert rows[0]["amount"] == "20.00"
    assert rows[1]["amount"] == "10.50"
