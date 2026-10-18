
import os
from io import BytesIO
from pathlib import Path

import pytesseract
from dotenv import load_dotenv
from PIL import Image

load_dotenv(
    Path(__file__).resolve().parent.parent / ".env"
)

# Optional explicit Windows executable path
tesseract_path = os.getenv("TESSERACT_CMD")

if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = (
        tesseract_path
    )


def extract_receipt_text(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6",
            timeout=15,
        )

    return text.strip()


def get_ocr_reader():
    return extract_receipt_text
