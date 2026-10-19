
from hashlib import sha256
from pathlib import PureWindowsPath
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Document
from .pdf_service import extract_pdf_text
from .s3_service import get_s3_client
from .auth import AuthUser, get_current_user

import os

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class DocumentRead(BaseModel):
    id: str
    filename: str
    size_bytes: int
    page_count: int
    status: str


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=201,
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    s3=Depends(get_s3_client),
    user: AuthUser = Depends(get_current_user),
):
    filename = PureWindowsPath(
        file.filename or ""
    ).name

    try:
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=415,
                detail="Only PDF files are supported",
            )

        if len(filename) > 255:
            raise HTTPException(
                status_code=400,
                detail="Filename is too long",
            )

        # Read at most 5 MB plus one extra byte.
        data = file.file.read(MAX_UPLOAD_BYTES + 1)

        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="PDF exceeds the 5 MB limit",
            )

        if not data.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=415,
                detail="Invalid PDF file",
            )

        try:
            page_count, extracted_text = extract_pdf_text(data)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    finally:
        file.file.close()

    document_id = str(uuid4())
    object_key = f"statements/{user.id}/{document_id}.pdf"

    status = (
        "text_ready"
        if extracted_text.strip()
        else "needs_ocr"
    )

    bucket = os.environ["AWS_S3_BUCKET"]

    try:
        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=data,
            ContentType="application/pdf",
            ServerSideEncryption="AES256",
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Document storage unavailable",
        ) from exc

    document = Document(
        id=document_id,
        user_id=user.id,
        filename=filename,
        s3_key=object_key,
        size_bytes=len(data),
        sha256=sha256(data).hexdigest(),
        page_count=page_count,
        status=status,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)

    except SQLAlchemyError as exc:
        db.rollback()

        # Best-effort cleanup if the DB write fails.
        try:
            s3.delete_object(
                Bucket=bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError):
            pass

        raise HTTPException(
            status_code=503,
            detail="Could not save document metadata",
        ) from exc

    return document
