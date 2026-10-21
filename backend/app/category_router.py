"""Owner-scoped, read-only ML suggestions for receipt drafts."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from .auth import AuthUser, get_current_user
from .category_service import CategorySuggester, get_category_suggester
from .database import get_db
from .models import Document, TransactionDraft

router = APIRouter(tags=["Receipt ML Suggestions"])


class ItemSuggestion(BaseModel):
    line_index: int
    source_line_index: int | None
    category: str | None
    source: Literal["sklearn", "ollama", "review"]
    model_score: float | None
    reason: str


class SuggestionBatch(BaseModel):
    draft_id: str
    requires_human_review: Literal[True] = True
    suggestions: list[ItemSuggestion]


@router.post(
    "/api/v1/drafts/{draft_id}/category-suggestions",
    response_model=SuggestionBatch,
)
def suggest_draft_categories(
    draft_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
    suggester: CategorySuggester = Depends(get_category_suggester),
):
    # Read the original draft server-side; don't accept client-supplied OCR evidence.
    # Read-only query: avoid holding a PostgreSQL row lock during LLM calls.
    draft = db.scalar(
        select(TransactionDraft).join(
            Document, TransactionDraft.document_id == Document.id
        ).where(
            TransactionDraft.id == draft_id,
            TransactionDraft.user_id == user.id,
            Document.user_id == user.id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    document = db.get(Document, draft.document_id)
    if not document.s3_key.startswith("receipts/"):
        raise HTTPException(status_code=422, detail="Suggestions require a receipt")
    if draft.status != "pending":
        raise HTTPException(status_code=409, detail="Draft is no longer pending")

    rows = draft.receipt_items or []
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many receipt items")

    output = []
    # Each fallback can take 10 seconds; bound calls per request.
    fallback_budget = 2
    for index, item in enumerate(rows):
        raw = item.get("raw_description") if isinstance(item, dict) else None
        # Manually added rows have no authentic source OCR text.
        if not isinstance(item, dict) or item.get("source_line_index") is None:
            raw = None
        suggestion = suggester.suggest(raw, allow_fallback=fallback_budget > 0)
        if suggestion["source"] == "ollama" or (
            suggestion["source"] == "review"
            and suggestion["reason"] in {"ollama_unavailable", "ollama_uncertain"}
        ):
            fallback_budget -= 1
        output.append(ItemSuggestion(
            line_index=index,
            source_line_index=item.get("source_line_index") if isinstance(item, dict) else None,
            **suggestion,
        ))

    # Critically: no db.commit(), no draft change, no items_reviewed=True.
    return SuggestionBatch(draft_id=draft_id, suggestions=output)
