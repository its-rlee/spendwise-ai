
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_transaction():
    response = client.post(
        "/api/v1/transactions/preview",
        json={
            "merchant": "Walmart",
            "amount": "85.50",
            "category": "Groceries"
        },
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "85.50"


def test_negative_amount_rejected():
    response = client.post(
        "/api/v1/transactions/preview",
        json={
            "merchant": "Walmart",
            "amount": "-10.00"
        },
    )

    assert response.status_code == 422


def test_optional_date_and_currency():
    response = client.post(
        "/api/v1/transactions/preview",
        json={
            "merchant": "Walmart",
            "amount": "85.50",
            "transaction_date": "2026-10-15",
            "currency": "USD",
        },
    )

    assert response.status_code == 200
    assert response.json()["transaction_date"] == "2026-10-15"
    assert response.json()["currency"] == "USD"


def test_whitespace_merchant():
    response = client.post(
        "/api/v1/transactions/preview",
        json={
            "merchant": "   ",
            "amount": "85.50",
        },
    )

    assert response.status_code == 422


def test_default_currency():
    response = client.post(
        "/api/v1/transactions/preview",
        json={
            "merchant": "Costco",
            "amount": "120.00",
        },
    )

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"
    assert response.json()["transaction_date"] is None

