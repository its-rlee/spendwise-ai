
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False
        },
        poolclass=StaticPool,
    )

    # Our real table uses the "spendwise" schema.
    # SQLite has no matching schema, so map it
    # to SQLite's default schema for these tests.
    test_engine = sqlite_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        with Session(test_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def test_create_and_read(client):
    response = client.post(
        "/api/v1/transactions",
        json={
            "merchant": "Walmart",
            "amount": "85.50",
            "category": "Groceries",
        },
    )

    assert response.status_code == 201

    transaction_id = response.json()["id"]

    response = client.get(
        f"/api/v1/transactions/{transaction_id}"
    )

    assert response.status_code == 200
    assert response.json()["merchant"] == "Walmart"


def test_update_and_delete(client):
    created = client.post(
        "/api/v1/transactions",
        json={
            "merchant": "Costco",
            "amount": "42.00",
        },
    )

    assert created.status_code == 201
    transaction_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"category": "Groceries"},
    )

    assert updated.status_code == 200
    assert updated.json()["category"] == "Groceries"

    deleted = client.delete(
        f"/api/v1/transactions/{transaction_id}"
    )

    assert deleted.status_code == 204

    missing = client.get(
        f"/api/v1/transactions/{transaction_id}"
    )

    assert missing.status_code == 404


def test_invalid_merchant(client):
    response = client.post(
        "/api/v1/transactions",
        json={
            "merchant": "   ",
            "amount": "20.00",
        },
    )

    assert response.status_code == 422
