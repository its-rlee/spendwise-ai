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
from app.finance_analytics import get_utc_today
from app.main import app
from app.models import Document, Transaction, TransactionItem


@pytest.fixture
def dashboard_client():
    raw = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine = raw.execution_options(schema_translate_map={"spendwise": None})
    Base.metadata.create_all(engine)

    alice, bob = str(uuid4()), str(uuid4())
    with Session(engine) as db:
        def purchase(owner, merchant, total, day, currency="USD",
                     direction="debit", category="Mixed Shopping"):
            transaction = Transaction(
                user_id=owner,
                merchant=merchant,
                amount=Decimal(total),
                category=category,
                transaction_date=day,
                currency=currency,
                direction=direction,
            )
            db.add(transaction)
            db.flush()
            return transaction

        oct_spending = purchase(alice, "October Store", "50.00", date(2026, 10, 18))
        old_costco = purchase(alice, "Costco Wholesale", "196.70", date(2023, 10, 26))
        purchase(alice, "September Shop", "20.00", date(2026, 9, 8))
        purchase(alice, "Late September", "5.00", date(2026, 9, 29))
        purchase(alice, "Paycheck", "100.00", date(2026, 10, 20),
                 direction="credit", category="Income")
        purchase(alice, "Euro Market", "10.00", date(2026, 10, 9),
                 currency="EUR")
        other_user = purchase(bob, "Private Store", "999.00", date(2026, 10, 18))
        db.add_all([
            TransactionItem(
                transaction_id=oct_spending.id,
                line_index=0, name="Chicken", category="Meat",
                amount=Decimal("12.00"),
            ),
            TransactionItem(
                transaction_id=oct_spending.id,
                line_index=1, name="Coffee", category="Beverages",
                amount=Decimal("22.00"),
            ),
            TransactionItem(
                transaction_id=old_costco.id,
                line_index=0, name="Kirkland Chicken", category="Meat",
                amount=Decimal("19.99"),
            ),
            TransactionItem(
                transaction_id=other_user.id,
                line_index=0, name="Private Products", category="Meat",
                amount=Decimal("700.00"),
            ),
        ])
        for user_id, status, suffix in [
            (alice, "uploaded", "pending"),
            (alice, "processed", "processed"),
            (bob, "uploaded", "private"),
        ]:
            db.add(Document(
                id=str(uuid4()),
                filename=f"{suffix}.jpg",
                s3_key=f"receipts/{user_id}/{suffix}.jpg",
                size_bytes=100,
                sha256="a" * 64,
                page_count=1,
                status=status,
                user_id=user_id,
            ))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_utc_today] = lambda: date(2026, 10, 22)
    client = TestClient(app)
    try:
        yield client, alice, bob
    finally:
        client.close()
        app.dependency_overrides.clear()
        raw.dispose()


def as_user(user_id):
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=user_id)


def test_dashboard_requires_login(dashboard_client):
    client, _, _ = dashboard_client
    assert client.get("/api/v1/dashboard").status_code == 401


def test_current_month_is_owner_scoped_and_fully_calculated(dashboard_client):
    client, alice, _ = dashboard_client
    as_user(alice)
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["month"] == "2026-10"
    assert data["this_month_expenses"] == "50.00"
    assert data["this_month_income"] == "100.00"
    assert data["this_month_net"] == "50.00"
    assert data["last_month_expenses"] == "25.00"
    assert data["same_point_last_month_expenses"] == "20.00"
    assert data["comparison_basis"] == "month_to_date"
    assert data["available_currencies"] == ["EUR", "USD"]
    assert data["pending_receipt_count"] == 1
    assert data["pending_receipts"][0]["filename"] == "pending.jpg"
    assert all(p["merchant"] != "Private Store" for p in data["recent_purchases"])
    assert any(p["merchant"] == "Costco Wholesale" for p in data["recent_purchases"])
    assert all(i["name"] != "Private Products" for p in data["recent_purchases"] for i in p["items"])


def test_item_categories_are_distinct_from_receipt_total(dashboard_client):
    client, alice, _ = dashboard_client
    as_user(alice)
    data = client.get("/api/v1/dashboard").json()
    assert data["item_categories"] == [
        {"category": "Beverages", "amount": "22.00"},
        {"category": "Meat", "amount": "12.00"},
    ]
    assert data["top_items"][0]["name"] == "Coffee"
    assert data["this_month_expenses"] == "50.00"
    assert data["monthly"][-1]["month"] == "2026-10"
    assert data["monthly"][-1]["expenses"] == "50.00"


def test_historical_month_shows_old_receipt_without_misattributing(dashboard_client):
    client, alice, _ = dashboard_client
    as_user(alice)
    response = client.get("/api/v1/dashboard?month=2023-10")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["comparison_basis"] == "full_month"
    assert data["month"] == "2023-10"
    assert data["this_month_expenses"] == "196.70"
    assert data["item_categories"][0] == {
        "category": "Meat",
        "amount": "19.99",
    }
    assert data["monthly"][-1]["month"] == "2023-10"


def test_currencies_never_mix_in_summary(dashboard_client):
    client, alice, _ = dashboard_client
    as_user(alice)
    data = client.get("/api/v1/dashboard?currency=EUR").json()
    assert data["this_month_expenses"] == "10.00"
    assert data["this_month_income"] == "0.00"
    assert data["item_categories"] == []
    assert any(p["currency"] == "USD" for p in data["recent_purchases"])


def test_separate_user_sees_only_own_data(dashboard_client):
    client, _, bob = dashboard_client
    as_user(bob)
    data = client.get("/api/v1/dashboard").json()
    assert data["this_month_expenses"] == "999.00"
    assert data["pending_receipt_count"] == 1
    assert [p["merchant"] for p in data["recent_purchases"]] == [
        "Private Store"
    ]


@pytest.mark.parametrize("query", [
    "?month=2026-13", "?month=2027-01",
    "?month=1999-12", "?month=nope", "?currency=US",
])
def test_reject_invalid_filter(dashboard_client, query):
    client, alice, _ = dashboard_client
    as_user(alice)
    assert client.get(f"/api/v1/dashboard{query}").status_code == 422
