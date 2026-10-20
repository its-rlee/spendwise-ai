
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PAGES = 10


def extract_pdf_text(data: bytes) -> tuple[int, str]:
    try:
        reader = PdfReader(BytesIO(data))

        if reader.is_encrypted:
            raise ValueError(
                "Password-protected PDFs are not supported"
            )

        page_count = len(reader.pages)

        if not 1 <= page_count <= MAX_PAGES:
            raise ValueError(
                f"PDF must contain 1 to {MAX_PAGES} pages"
            )

        text_parts = []

        for page in reader.pages:
            text_parts.append(page.extract_text() or "")

        return page_count, "\n".join(text_parts)

    except PdfReadError as exc:
        raise ValueError(
            "PDF could not be parsed"
        ) from exc
