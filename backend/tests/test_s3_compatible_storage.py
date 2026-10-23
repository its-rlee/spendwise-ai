"""Offline regression checks for AWS/Supabase S3-compatible configuration."""
from botocore.config import Config

from app.s3_service import get_s3_client


def test_s3_endpoint_uses_signature_v4_path_addressing(monkeypatch):
    captured = {}

    def fake_client(service, **kwargs):
        captured.update({"service": service, **kwargs})
        return object()

    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv(
        "AWS_S3_ENDPOINT_URL",
        "https://example.storage.supabase.co/storage/v1/s3",
    )
    monkeypatch.setattr("app.s3_service.boto3.client", fake_client)

    get_s3_client()

    assert captured["service"] == "s3"
    assert captured["endpoint_url"].startswith("https://")
    assert captured["region_name"] == "us-east-1"
    assert isinstance(captured["config"], Config)
    assert captured["config"].signature_version == "s3v4"
    assert captured["config"].s3["addressing_style"] == "path"


def test_aws_s3_endpoint_is_optional(monkeypatch):
    captured = {}

    def fake_client(service, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.delenv("AWS_S3_ENDPOINT_URL", raising=False)
    monkeypatch.setattr("app.s3_service.boto3.client", fake_client)

    get_s3_client()

    assert captured["endpoint_url"] is None
    assert captured["region_name"] == "us-west-2"
