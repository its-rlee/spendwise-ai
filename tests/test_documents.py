
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.s3_service import get_s3_client
from tests.auth_helpers import override_current_user


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


@pytest.fixture
def client(monkeypatch):
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

    def override_get_db():
        with Session(test_engine) as db:
            yield db

    fake_s3 = FakeS3()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_s3_client] = (
        lambda: fake_s3
    )
    override_current_user()

    try:
        with TestClient(app) as test_client:
            yield test_client, fake_s3
    finally:
        app.dependency_overrides.clear()
        sqlite_engine.dispose()


def make_test_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()


def test_upload_valid_pdf(client):
    test_client, fake_s3 = client

    response = test_client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "statement.pdf",
                make_test_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    result = response.json()

    assert result["filename"] == "statement.pdf"
    assert result["page_count"] == 1
    assert result["status"] == "needs_ocr"
    assert len(fake_s3.objects) == 1


def test_reject_invalid_pdf(client):
    test_client, fake_s3 = client

    response = test_client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "fake.pdf",
                b"This is not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 415
    assert len(fake_s3.objects) == 0


def test_reject_oversized_pdf(client):
    test_client, fake_s3 = client

    response = test_client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "large.pdf",
                b"%PDF-" + b"x" * (5 * 1024 * 1024),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert len(fake_s3.objects) == 0
