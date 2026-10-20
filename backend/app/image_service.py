
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 10_000_000


def normalize_receipt_image(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG"):
                raise ValueError(
                    "Only JPEG and PNG images are supported"
                )

            width, height = image.size

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "Image resolution is too large"
                )

            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")

            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=85,
            )

            normalized = output.getvalue()

            if len(normalized) > MAX_UPLOAD_BYTES:
                raise ValueError(
                    "Normalized image is too large"
                )

            return normalized

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(
            "Could not decode receipt image"
        ) from exc
    except Image.DecompressionBombError as exc:
        raise ValueError(
            "Unsafe image dimensions"
        ) from exc
