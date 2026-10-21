"""Day 5: classifier, bounded fallback and owner-scoped review preview tests."""
from uuid import uuid4

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import AuthUser, get_current_user
from app.category_service import CategorySuggester, get_category_suggester
from app.database import Base, get_db
from app.main import app
from app.models import Document, TransactionDraft


class FakeClassifier:
    classes_ = np.array(["Dairy", "Meat"])

    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, rows):
        return np.array([self.probability for _ in rows])


def test_good_model_score_returns_review_only(monkeypatch):
    monkeypatch.setattr(CategorySuggester, "__init__", lambda self: None)
    service = CategorySuggester()
    service.model = FakeClassifier([0.95, 0.05])
    service.threshold = 0.55
    service.fallback_enabled = False
    result = service.suggest("KS ORG MLK", allow_fallback=True)
    assert result["category"] == "Dairy"
    assert result["source"] == "sklearn"
    assert result["reason"] == "review_required"


def test_ollama_timeout_falls_back_to_human_review(monkeypatch):
    monkeypatch.setattr(CategorySuggester, "__init__", lambda self: None)
    service = CategorySuggester()
    service.model = FakeClassifier([0.52, 0.48])
    service.threshold = 0.60
    service.fallback_enabled = True

    def fail(raw):
        raise httpx.ReadTimeout("Timed out")

    monkeypatch.setattr(service, "_ollama_category", fail)
    result = service.suggest("UNKNOWN ABBR", allow_fallback=True)
    assert result["source"] == "review"
    assert result["category"] is None
    assert result["reason"] == "ollama_unavailable"


@pytest.fixture
def api(monkeypatch):
    raw_engine = create_engine("sqlite+pysqlite:///:memory:",
                               connect_args={"check_same_thread": False}, poolclass=StaticPool)
    engine = raw_engine.execution_options(schema_translate_map={"spendwise": None})
    Base.metadata.create_all(bind=engine)
    owner, other, document_id, draft_id = (str(uuid4()) for _ in range(4))
    with Session(engine) as db:
        db.add(Document(id=document_id, user_id=owner, filename="receipt.jpg",
                        s3_key=f"receipts/{owner}/{document_id}.jpg", size_bytes=100,
                        sha256="a" * 64, page_count=1, status="awaiting_review"))
        db.add(TransactionDraft(
            id=draft_id, document_id=document_id, user_id=owner, source_index=0,
            status="pending", items_reviewed=False,
            receipt_items=[
                {"source_line_index": 0, "raw_description": "KS ORG MLK",
                 "name": "Organic milk", "amount": "4.99", "category": "Dairy"},
                {"source_line_index": None, "raw_description": None,
                 "name": "Manually added", "amount": "1.00", "category": "Other"},
            ],
        ))
        db.commit()

    identity = {"id": owner}

    def override_db():
        with Session(engine) as db:
            yield db

    class FakeService:
        def suggest(self, raw, *, allow_fallback):
            if raw:
                return {"category": "Dairy", "source": "sklearn",
                        "model_score": 0.95, "reason": "review_required"}
            return {"category": None, "source": "review",
                    "model_score": None, "reason": "missing_original_text"}

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id=identity["id"])
    app.dependency_overrides[get_category_suggester] = lambda: FakeService()
    client = TestClient(app)
    yield client, engine, draft_id, identity, owner, other
    client.close()
    app.dependency_overrides.clear()
    raw_engine.dispose()


def test_suggestions_do_not_approve_or_persist(api):
    client, engine, draft_id, _, _, _ = api
    response = client.post(f"/api/v1/drafts/{draft_id}/category-suggestions", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_human_review"] is True
    assert body["suggestions"][0]["category"] == "Dairy"
    assert body["suggestions"][1]["category"] is None
    with Session(engine) as db:
        draft = db.get(TransactionDraft, draft_id)
        assert draft.items_reviewed is False
        assert draft.status == "pending"
        assert draft.receipt_items[0]["raw_description"] == "KS ORG MLK"


def test_other_user_cannot_get_suggestions(api):
    client, _, draft_id, identity, _, other = api
    identity["id"] = other
    response = client.post(f"/api/v1/drafts/{draft_id}/category-suggestions", json={})
    assert response.status_code == 404
