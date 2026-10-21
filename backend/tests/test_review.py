
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Document, Transaction
from app.extraction_schemas import ReceiptExtraction
from app.s3_service import get_s3_client
from app.ocr_service import get_ocr_reader
from app.llm_service import get_extractor
from tests.auth_helpers import TEST_USER_ID, override_current_user


@pytest.fixture
def review_client(monkeypatch):
    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    engine = sqlite_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=engine)

    document_id = str(uuid4())

    with Session(engine) as db:
        db.add(
            Document(
                id=document_id,
                user_id=TEST_USER_ID,
                filename="fictional-receipt.jpg",
                s3_key=f"receipts/{document_id}.jpg",
                size_bytes=100,
                sha256="a" * 64,
                page_count=1,
                status="text_ready",
            )
        )
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    def fake_extraction(**kwargs):
        return ReceiptExtraction(
            merchant="WALMART STORE",
            purchase_date=date(2026, 10, 15),
            currency=None,
            total=Decimal("85.50"),
        )

    monkeypatch.setattr(
        "app.review.run_document_extraction",
        fake_extraction,
    )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_s3_client] = (
        lambda: object()
    )
    app.dependency_overrides[get_ocr_reader] = (
        lambda: lambda data: "TEST RECEIPT"
    )
    app.dependency_overrides[get_extractor] = (
        lambda: object()
    )
    override_current_user()

    client = TestClient(app)

    try:
        yield client, engine, document_id
    finally:
        client.close()
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def approval_payload():
    return {
        "merchant": "WALMART STORE",
        "amount": "85.50",
        "transaction_date": "2026-10-15",
        "direction": "debit",
        "currency": "USD",
        "category": "Groceries",
        "confirm_similar": False,
    }


def prepare(client, document_id):
    return client.post(
        f"/api/v1/documents/{document_id}/prepare"
    )


def review_empty_receipt_items(client, draft_id):
    response = client.patch(
        f"/api/v1/drafts/{draft_id}/items",
        json={"items": []},
    )

    assert response.status_code == 200, response.text
    assert response.json()["items_reviewed"] is True



def test_prepare_does_not_approve(review_client):
    client, engine, document_id = review_client

    response = prepare(client, document_id)

    assert response.status_code == 201
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(Transaction.id))
        )

    assert count == 0


def test_approve_and_prevent_repeat(review_client):
    client, engine, document_id = review_client

    prepared = prepare(client, document_id)
    draft_id = prepared.json()[0]["id"]
    review_empty_receipt_items(client, draft_id)

    url = f"/api/v1/drafts/{draft_id}/approve"

    first = client.post(
        url,
        json=approval_payload(),
    )

    assert first.status_code == 201

    second = client.post(
        url,
        json=approval_payload(),
    )

    assert second.status_code == 409

    with Session(engine) as db:
        transactions = db.scalars(
            select(Transaction)
        ).all()

        document = db.get(Document, document_id)

        assert len(transactions) == 1
        assert transactions[0].direction == "debit"
        assert transactions[0].amount == Decimal("85.50")
        assert transactions[0].source_document_id == document_id
        assert document.status == "processed"


def test_missing_currency_rejected(review_client):
    client, _, document_id = review_client

    prepared = prepare(client, document_id)
    draft_id = prepared.json()[0]["id"]

    payload = approval_payload()
    del payload["currency"]

    response = client.post(
        f"/api/v1/drafts/{draft_id}/approve",
        json=payload,
    )

    assert response.status_code == 422


def test_prepare_twice_rejected(review_client):
    client, _, document_id = review_client

    first = prepare(client, document_id)
    second = prepare(client, document_id)

    assert first.status_code == 201
    assert second.status_code == 409


def test_possible_duplicate_warning(review_client):
    client, engine, document_id = review_client

    prepared = prepare(client, document_id)
    draft_id = prepared.json()[0]["id"]
    review_empty_receipt_items(client, draft_id)    

    # Simulate an existing purchase with
    # the same merchant, amount and date.
    with Session(engine) as db:
        db.add(
            Transaction(
                user_id=TEST_USER_ID,
                merchant="WALMART STORE",
                amount=Decimal("85.50"),
                transaction_date=date(2026, 10, 15),
                currency="USD",
                direction="debit",
                category="Groceries",
            )
        )
        db.commit()

    url = f"/api/v1/drafts/{draft_id}/approve"

    blocked = client.post(
        url,
        json=approval_payload(),
    )

    assert blocked.status_code == 409

    payload = approval_payload()
    payload["confirm_similar"] = True

    confirmed = client.post(
        url,
        json=payload,
    )

    assert confirmed.status_code == 201
