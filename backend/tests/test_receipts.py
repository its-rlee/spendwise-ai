
from io import BytesIO
from uuid import uuid4
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Document, Transaction, TransactionDraft
from tests.auth_helpers import TEST_USER_ID
from app.auth import get_current_user
from app.ocr_service import get_ocr_reader
from app.s3_service import get_s3_client
from tests.auth_helpers import override_current_user


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def make_image(image_format="JPEG"):
    image = Image.new(
        "RGB",
        (800, 500),
        "white",
    )

    output = BytesIO()
    image.save(output, format=image_format)

    return output.getvalue()


@pytest.fixture
def setup_client(monkeypatch):
    monkeypatch.setenv(
        "AWS_S3_BUCKET",
        "spendwise-test-bucket",
    )

    monkeypatch.setenv("RECEIPT_AI_PROVIDER", "ollama")

    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    test_engine = sqlite_engine.execution_options(
        schema_translate_map={"spendwise": None}
    )

    Base.metadata.create_all(bind=test_engine)

    def override_db():
        with Session(test_engine) as db:
            yield db

    fake_s3 = FakeS3()

    def fake_ocr(image_bytes):
        return "TEST STORE\nMILK 4.99\nTOTAL 4.99"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_s3_client] = (
        lambda: fake_s3
    )
    app.dependency_overrides[get_ocr_reader] = (
        lambda: fake_ocr
    )
    override_current_user()

    client = TestClient(app)

    try:
        yield client, fake_s3, test_engine
    finally:
        client.close()
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def test_upload_receipt(setup_client):
    client, fake_s3, engine = setup_client

    response = client.post(
        "/api/v1/receipts/upload",
        files={
            "file": (
                "receipt.jpg",
                make_image(),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "text_ready"
    assert "MILK 4.99" in data["ocr_text"]
    assert len(fake_s3.objects) == 1

    with Session(engine) as db:
        saved = db.get(Document, data["document_id"])
        assert saved is not None
        assert saved.s3_key.startswith("receipts/")


def test_invalid_image(setup_client):
    client, fake_s3, _ = setup_client

    response = client.post(
        "/api/v1/receipts/upload",
        files={
            "file": (
                "fake.jpg",
                b"not a real image",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 422
    assert len(fake_s3.objects) == 0


def test_png_upload(setup_client):
    client, fake_s3, _ = setup_client

    response = client.post(
        "/api/v1/receipts/upload",
        files={
            "file": (
                "receipt.png",
                make_image("PNG"),
                "image/png",
            )
        },
    )

    assert response.status_code == 201
    assert len(fake_s3.objects) == 1


def test_oversized_upload(setup_client):
    client, fake_s3, _ = setup_client

    response = client.post(
        "/api/v1/receipts/upload",
        files={
            "file": (
                "large.jpg",
                b"x" * (5 * 1024 * 1024 + 1),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
    assert len(fake_s3.objects) == 0


def _upload_test_receipt(client):
    response = client.post(
        "/api/v1/receipts/upload",
        files={"file": ("pending.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def test_delete_unfinished_receipt_removes_image_metadata_and_drafts(setup_client):
    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)

    draft_id = str(uuid4())
    with Session(engine) as db:
        doc = db.get(Document, document_id)
        doc.status = "awaiting_review"
        db.add(TransactionDraft(
            id=draft_id,
            document_id=document_id,
            source_index=0,
            user_id=TEST_USER_ID,
            status="pending",
        ))
        db.commit()

    response = client.delete(f"/api/v1/receipts/{document_id}")
    assert response.status_code == 204, response.text
    assert response.content == b""
    assert fake_s3.objects == {}

    with Session(engine) as db:
        assert db.get(Document, document_id) is None
        assert db.get(TransactionDraft, draft_id) is None

    # Repeated DELETE is not allowed to reach other users or objects.
    assert client.delete(f"/api/v1/receipts/{document_id}").status_code == 404


def test_delete_refuses_other_users_receipt_without_touching_s3(setup_client):
    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)
    original_objects = dict(fake_s3.objects)
    override_current_user("22222222-2222-2222-2222-222222222222")
    try:
        response = client.delete(f"/api/v1/receipts/{document_id}")
        assert response.status_code == 404
        assert fake_s3.objects == original_objects
        with Session(engine) as db:
            assert db.get(Document, document_id) is not None
    finally:
        override_current_user()


def test_delete_refuses_receipt_with_saved_transaction(setup_client):
    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)
    with Session(engine) as db:
        db.get(Document, document_id).status = "awaiting_review"
        db.add(Transaction(
            user_id=TEST_USER_ID,
            merchant="Test Merchant",
            category="Shopping",
            currency="USD",
            amount=Decimal("18.50"),
            direction="debit",
            transaction_date=date(2026, 10, 22),
            source_document_id=document_id,
            source_index=0,
        ))
        db.commit()
    original_objects = dict(fake_s3.objects)
    response = client.delete(f"/api/v1/receipts/{document_id}")
    assert response.status_code == 409
    assert fake_s3.objects == original_objects
    with Session(engine) as db:
        assert db.get(Document, document_id) is not None


def test_delete_refuses_processed_receipt(setup_client):
    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)
    with Session(engine) as db:
        db.get(Document, document_id).status = "processed"
        db.commit()
    response = client.delete(f"/api/v1/receipts/{document_id}")
    assert response.status_code == 409
    assert len(fake_s3.objects) == 1


def test_delete_storage_failure_preserves_db_metadata(setup_client, monkeypatch):
    from botocore.exceptions import ClientError

    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)

    def fail_delete(Bucket, Key):
        raise ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Unavailable"}},
            "DeleteObject",
        )

    monkeypatch.setattr(fake_s3, "delete_object", fail_delete)
    response = client.delete(f"/api/v1/receipts/{document_id}")
    assert response.status_code == 503

    with Session(engine) as db:
        assert db.get(Document, document_id) is not None
    assert len(fake_s3.objects) == 1


def test_delete_unapproved_doc_requires_authenticated_user(setup_client):
    from app.main import app

    client, fake_s3, engine = setup_client
    document_id = _upload_test_receipt(client)
    override = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.delete(f"/api/v1/receipts/{document_id}")
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides[get_current_user] = override

    assert len(fake_s3.objects) == 1
