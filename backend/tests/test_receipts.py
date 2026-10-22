
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Document
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
