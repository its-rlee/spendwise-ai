
import os
import logging
from hashlib import sha256

import httpx
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from .database import get_db
from .models import Document
from .pdf_service import extract_pdf_text
from .ocr_service import get_ocr_reader
from .s3_service import get_s3_client
from .llm_service import (
    ModelOutputError,
    get_extractor,
)
from .extraction_schemas import (
    ReceiptExtraction,
    StatementExtraction,
)

from .auth import AuthUser, get_current_user
from .ownership import get_owned_document

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["AI Extraction"],
)

logger = logging.getLogger(__name__)

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 12000


@router.post(
    "/{document_id}/extract",
    response_model=(
        ReceiptExtraction | StatementExtraction
    ),
)
def extract_document(
    document_id: str,
    db: Session = Depends(get_db),
    s3=Depends(get_s3_client),
    ocr_reader=Depends(get_ocr_reader),
    extractor=Depends(get_extractor),
    user: AuthUser = Depends(get_current_user)
):
    return run_document_extraction(
        document_id=document_id,
        db=db,
        s3=s3,
        ocr_reader=ocr_reader,
        extractor=extractor,
        user_id=user.id
    )

def run_document_extraction(
    document_id: str,
    db: Session,
    s3,
    ocr_reader,
    extractor,
    user_id: str,
):
    document = get_owned_document(
        db,
        document_id,
        user_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.s3_key.startswith("receipts/"):
        kind = "receipt"

    elif document.s3_key.startswith("statements/"):
        kind = "statement"

    else:
        raise HTTPException(
            status_code=422,
            detail="Unsupported document type",
        )

    try:
        response = s3.get_object(
            Bucket=os.environ["AWS_S3_BUCKET"],
            Key=document.s3_key,
        )

        body = response["Body"]

        try:
            data = body.read(
                MAX_DOCUMENT_BYTES + 1
            )
        finally:
            body.close()

    except (ClientError, BotoCoreError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve document",
        ) from exc

    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Stored document is too large",
        )

    if sha256(data).hexdigest() != document.sha256:
        raise HTTPException(
            status_code=409,
            detail="Document integrity check failed",
        )

    if kind == "receipt":
        try:
            text = ocr_reader(data)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="OCR processing failed",
            ) from exc

    else:
        try:
            _, text = extract_pdf_text(data)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text; OCR required",
        )

    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=422,
            detail="Document exceeds text limit",
        )

    try:
        return extractor.extract(kind, text)

    except (httpx.HTTPError, ModelOutputError) as exc:
        logger.exception("LLM extraction failed")

        raise HTTPException(
            status_code=502,
            detail="LLM extraction failed",
        ) from exc