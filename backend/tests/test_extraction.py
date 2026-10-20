
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Document
from app.s3_service import get_s3_client
from app.ocr_service import get_ocr_reader
from app.llm_service import get_extractor
from app.extraction_schemas import ReceiptExtraction
from app.extraction_validation import review_receipt
from tests.auth_helpers import TEST_USER_ID, override_current_user


def test_invalid_negative_total():
    with pytest.raises(ValidationError):
        ReceiptExtraction(
            merchant="Walmart",
            total=Decimal("-19.90"),
        )


def test_inconsistent_receipt_total():
    receipt = ReceiptExtraction(
        merchant="Walmart",
        purchase_date=date(2026, 10, 17),
        currency="USD",
        subtotal=Decimal("20.00"),
        tax=Decimal("2.00"),
        total=Decimal("32.00"),
    )

    result = review_receipt(receipt)

    assert result.needs_review is True
    assert any(
        "does not match" in reason
        for reason in result.review_reasons
    )


class FakeS3:
    def __init__(self, data):
        self.data = data

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.data)}


class FakeExtractor:
    def extract(self, kind, text):
        assert kind == "receipt"
        assert "WALMART" in text

        return ReceiptExtraction(
            merchant="WALMART",
            purchase_date=date(2026, 10, 17),
            currency="USD",
            total=Decimal("9.19"),
        )


@pytest.fixture
def extraction_client(monkeypatch):
    monkeypatch.setenv(
        "AWS_S3_BUCKET",
        "spendwise-test-bucket",
    )

    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    test_engine = sqlite_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=test_engine)

    sample_bytes = b"synthetic-receipt-image"
    document_id = str(uuid4())

    with Session(test_engine) as db:
        db.add(
            Document(
                id=document_id,
                user_id=TEST_USER_ID,
                filename="test.jpg",
                s3_key=f"receipts/{document_id}.jpg",
                size_bytes=len(sample_bytes),
                sha256=sha256(
                    sample_bytes
                ).hexdigest(),
                page_count=1,
                status="text_ready",
            )
        )
        db.commit()

    def override_db():
        with Session(test_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_s3_client] = (
        lambda: FakeS3(sample_bytes)
    )
    app.dependency_overrides[get_ocr_reader] = (
        lambda: lambda data: "WALMART\nTOTAL 9.19"
    )
    app.dependency_overrides[get_extractor] = (
        lambda: FakeExtractor()
    )
    override_current_user()

    client = TestClient(app)

    try:
        yield client, document_id
    finally:
        client.close()
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def test_extract_receipt(extraction_client):
    client, document_id = extraction_client

    response = client.post(
        f"/api/v1/documents/{document_id}/extract"
    )

    assert response.status_code == 200
    assert response.json()["kind"] == "receipt"
    assert response.json()["merchant"] == "WALMART"
    assert response.json()["total"] == "9.19"


def test_unknown_document(extraction_client):
    client, _ = extraction_client

    response = client.post(
        "/api/v1/documents/nonexistent/extract"
    )

    assert response.status_code == 404


def test_tax_percentage_handling():
    raw_output = {
        "kind": "receipt",
        "merchant": "Walmart",
        "tax": "8.00%",
        "total": "32.40",
    }

    result = ReceiptExtraction.model_validate(
        raw_output
    )

    assert result.tax is None
    assert result.tax_rate_percent == Decimal("8.00")
    assert result.needs_review is True
    assert "Tax rate supplied instead of tax amount" in (
        result.review_reasons
    )

