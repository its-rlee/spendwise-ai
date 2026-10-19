
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
from app.models import (
    Document,
    Transaction,
    TransactionDraft,
)


USER_A = str(uuid4())
USER_B = str(uuid4())


@pytest.fixture
def security_client():
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
    draft_id = str(uuid4())

    with Session(engine) as db:
        db.add(
            Document(
                id=document_id,
                user_id=USER_A,
                filename="test.pdf",
                s3_key=f"statements/{document_id}.pdf",
                size_bytes=100,
                sha256="a" * 64,
                page_count=1,
                status="awaiting_review",
            )
        )

        db.add(
            Transaction(
                user_id=USER_A,
                merchant="Walmart",
                amount=Decimal("85.50"),
                category="Groceries",
                currency="USD",
                direction="debit",
                transaction_date=date(2026, 10, 15),
            )
        )

        db.add(
            TransactionDraft(
                id=draft_id,
                user_id=USER_A,
                document_id=document_id,
                source_index=0,
                merchant="Walmart",
                amount=Decimal("85.50"),
                direction="debit",
                currency="USD",
                transaction_date=date(2026, 10, 15),
                review_reasons=[],
                status="pending",
            )
        )

        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)

    try:
        yield client, document_id, draft_id
    finally:
        client.close()
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def as_user(user_id):
    app.dependency_overrides[get_current_user] = (
        lambda: AuthUser(id=user_id)
    )


def test_no_token_rejected(security_client):
    client, _, _ = security_client

    response = client.get(
        "/api/v1/transactions"
    )

    assert response.status_code == 401


def test_owner_can_read_transaction(security_client):
    client, _, _ = security_client
    as_user(USER_A)

    response = client.get(
        "/api/v1/transactions"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_other_user_cannot_read_transaction(
    security_client,
):
    client, _, _ = security_client
    as_user(USER_B)

    response = client.get(
        "/api/v1/transactions"
    )

    assert response.status_code == 200
    assert response.json() == []

    response = client.get(
        "/api/v1/transactions/1"
    )

    assert response.status_code == 404


def test_other_user_cannot_approve_draft(
    security_client,
):
    client, _, draft_id = security_client
    as_user(USER_B)

    response = client.post(
        f"/api/v1/drafts/{draft_id}/approve",
        json={
            "merchant": "Walmart",
            "amount": "85.50",
            "transaction_date": "2026-10-15",
            "direction": "debit",
            "currency": "USD",
            "category": "Groceries",
        },
    )

    assert response.status_code == 404
