
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import AuthUser, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import (
    Document,
    Transaction,
    TransactionItem,
)
from app.extraction_schemas import (
    ReceiptExtraction,
    ReceiptItem,
)
from app.s3_service import get_s3_client
from app.ocr_service import get_ocr_reader
from app.llm_service import get_extractor


@pytest.fixture
def receipt_client(monkeypatch):
    raw_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    engine = raw_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=engine)

    alice = str(uuid4())
    bob = str(uuid4())
    document_id = str(uuid4())

    with Session(engine) as db:
        db.add(Document(
            id=document_id,
            user_id=alice,
            filename="fictional-receipt.jpg",
            s3_key=f"receipts/{alice}/{document_id}.jpg",
            size_bytes=100,
            sha256="a" * 64,
            page_count=1,
            status="text_ready",
        ))
        db.commit()

    identity = {"id": alice}

    def override_db():
        with Session(engine) as db:
            yield db

    def fake_extraction(**kwargs):
        return ReceiptExtraction(
            merchant="SPENDWISE TEST STORE",
            purchase_date=date(2026, 10, 19),
            currency="USD",
            subtotal=Decimal("8.49"),
            tax=Decimal("0.70"),
            total=Decimal("9.19"),
            items=[
                ReceiptItem(
                    name="Milk",
                    price=Decimal("4.99"),
                ),
                ReceiptItem(
                    name="Bread",
                    price=Decimal("3.50"),
                ),
            ],
        )

    monkeypatch.setattr(
        "app.review.run_document_extraction",
        fake_extraction,
    )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = (
        lambda: AuthUser(id=identity["id"])
    )
    app.dependency_overrides[get_s3_client] = lambda: object()
    app.dependency_overrides[get_ocr_reader] = (
        lambda: object()
    )
    app.dependency_overrides[get_extractor] = (
        lambda: object()
    )

    client = TestClient(app)

    try:
        yield client, engine, document_id, identity, alice, bob
    finally:
        client.close()
        app.dependency_overrides.clear()
        raw_engine.dispose()


def prepare(client, document_id):
    response = client.post(
        f"/api/v1/documents/{document_id}/prepare"
    )
    assert response.status_code == 201, response.text
    return response.json()[0]["id"]


def item_payload():
    return {
        "items": [
            {
                "name": "Milk",
                "amount": "4.99",
                "category": "Dairy",
            },
            {
                "name": "Bread",
                "amount": "3.50",
                "category": "Bakery",
            },
        ]
    }


def approval_payload():
    return {
        "merchant": "SPENDWISE TEST STORE",
        "amount": "9.19",
        "currency": "USD",
        "transaction_date": "2026-10-19",
        "direction": "debit",
        "category": "Groceries",
    }


def test_items_saved_only_after_approval(receipt_client):
    client, engine, document_id, _, _, _ = receipt_client

    draft_id = prepare(client, document_id)

    with Session(engine) as db:
        assert db.scalars(
            select(TransactionItem)
        ).all() == []

    approval_url = f"/api/v1/drafts/{draft_id}/approve"

    # Must review items first.
    response = client.post(
        approval_url,
        json=approval_payload(),
    )
    assert response.status_code == 409

    # User corrects and categorizes items.
    response = client.patch(
        f"/api/v1/drafts/{draft_id}/items",
        json=item_payload(),
    )
    assert response.status_code == 200
    assert response.json()["items_reviewed"] is True

    response = client.post(
        approval_url,
        json=approval_payload(),
    )
    assert response.status_code == 201, response.text

    with Session(engine) as db:
        transactions = db.scalars(
            select(Transaction)
        ).all()

        items = db.scalars(
            select(TransactionItem)
            .order_by(TransactionItem.line_index)
        ).all()

        assert len(transactions) == 1
        assert len(items) == 2

        assert transactions[0].amount == Decimal("9.19")
        assert items[0].category == "Dairy"
        assert items[1].category == "Bakery"

        assert sum(
            (item.amount for item in items),
            Decimal("0.00"),
        ) == Decimal("8.49")

        assert all(
            item.transaction_id == transactions[0].id
            for item in items
        )

    # Cannot save them again by approving twice.
    repeated = client.post(
        approval_url,
        json=approval_payload(),
    )
    assert repeated.status_code == 409


def test_other_user_cannot_edit_items(receipt_client):
    client, _, document_id, identity, _, bob = receipt_client

    draft_id = prepare(client, document_id)

    identity["id"] = bob

    response = client.patch(
        f"/api/v1/drafts/{draft_id}/items",
        json=item_payload(),
    )

    assert response.status_code == 404


def test_negative_item_amount_rejected(receipt_client):
    client, _, document_id, _, _, _ = receipt_client

    draft_id = prepare(client, document_id)
    payload = item_payload()
    payload["items"][0]["amount"] = "-4.99"

    response = client.patch(
        f"/api/v1/drafts/{draft_id}/items",
        json=payload,
    )

    assert response.status_code == 422


def test_item_subtotal_mismatch_requires_confirmation(
    receipt_client,
):
    client, _, document_id, _, _, _ = receipt_client

    draft_id = prepare(client, document_id)

    payload = item_payload()
    payload["items"][0]["amount"] = "5.99"

    saved = client.patch(
        f"/api/v1/drafts/{draft_id}/items",
        json=payload,
    )
    assert saved.status_code == 200

    url = f"/api/v1/drafts/{draft_id}/approve"

    blocked = client.post(
        url,
        json=approval_payload(),
    )
    assert blocked.status_code == 409

    confirmed = approval_payload()
    confirmed["confirm_item_mismatch"] = True

    accepted = client.post(
        url,
        json=confirmed,
    )
    assert accepted.status_code == 201
