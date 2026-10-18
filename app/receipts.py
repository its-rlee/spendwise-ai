
import os
from hashlib import sha256
from pathlib import PurePath
from uuid import uuid4

import pytesseract
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
from .image_service import (
    MAX_UPLOAD_BYTES,
    normalize_receipt_image,
)
from .models import Document
from .ocr_service import get_ocr_reader
from .s3_service import get_s3_client


router = APIRouter(
    prefix="/api/v1/receipts",
    tags=["Receipts"],
)


class ReceiptUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    ocr_text: str


@router.post(
    "/upload",
    response_model=ReceiptUploadResponse,
    status_code=201,
)
def upload_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    s3=Depends(get_s3_client),
    ocr_reader=Depends(get_ocr_reader),
):
    filename = PurePath(
        (file.filename or "receipt.jpg").replace(
            "\\", "/"
        )
    ).name

    try:
        if len(filename) > 255:
            raise HTTPException(
                status_code=400,
                detail="Filename is too long",
            )

        if not filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            raise HTTPException(
                status_code=415,
                detail="Only JPEG/PNG files are supported",
            )

        raw_data = file.file.read(
            MAX_UPLOAD_BYTES + 1
        )

        if len(raw_data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="File exceeds 5 MB",
            )

        try:
            image_bytes = normalize_receipt_image(
                raw_data
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    finally:
        file.file.close()

    # Local OCR: no Textract API request
    try:
        extracted_text = ocr_reader(image_bytes)

    except (
        pytesseract.TesseractNotFoundError,
        pytesseract.TesseractError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail="Local OCR processing failed",
        ) from exc

    document_id = str(uuid4())
    object_key = f"receipts/{document_id}.jpg"
    bucket = os.environ["AWS_S3_BUCKET"]

    try:
        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/jpeg",
            ServerSideEncryption="AES256",
        )

    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=502,
            detail="S3 upload failed",
        ) from exc

    document = Document(
        id=document_id,
        filename=filename,
        s3_key=object_key,
        size_bytes=len(image_bytes),
        sha256=sha256(image_bytes).hexdigest(),
        page_count=1,
        status=(
            "text_ready"
            if extracted_text
            else "needs_review"
        ),
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)

    except SQLAlchemyError as exc:
        db.rollback()

        # Best-effort cleanup if DB insertion fails
        try:
            s3.delete_object(
                Bucket=bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError):
            pass

        raise HTTPException(
            status_code=503,
            detail="Could not save receipt metadata",
        ) from exc

    return ReceiptUploadResponse(
        document_id=document_id,
        filename=filename,
        status=document.status,
        ocr_text=extracted_text,
    )
