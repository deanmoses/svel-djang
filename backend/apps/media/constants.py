"""Media app constants: formats, dimensions, and upload limits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageFormat:
    """Encoding parameters for a web-native image format."""

    content_type: str
    extension: str
    quality: int | None = None
    optimize: bool = False


# Pillow format name -> output encoding params.
WEB_NATIVE_FORMATS: dict[str, ImageFormat] = {
    "JPEG": ImageFormat(
        content_type="image/jpeg", extension="jpg", quality=85, optimize=True
    ),
    "PNG": ImageFormat(content_type="image/png", extension="png", optimize=True),
    "WEBP": ImageFormat(content_type="image/webp", extension="webp", quality=80),
    "AVIF": ImageFormat(content_type="image/avif", extension="avif", quality=63),
}

WEBP_FORMAT = WEB_NATIVE_FORMATS["WEBP"]

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",  # Web-native
    ".heic",
    ".heif",  # iPhone photos
    ".avif",  # Modern compression
    ".bmp",  # Legacy, converted to JPEG
}
# Keep in sync: frontend/src/lib/api/media-api.ts

# Rendition dimensions (longest side).
THUMB_MAX_DIMENSION = 400
DISPLAY_MAX_DIMENSION = 1600

# Validation bounds.
MIN_IMAGE_DIMENSION = 2  # reject degenerate 0x0, 1x1
MAX_IMAGE_DIMENSION = 20000  # prevent memory bombs during processing

# Upload limits.
# Keep in sync: frontend/src/lib/api/media-api.ts
MAX_IMAGE_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_UPLOADS_PER_HOUR = 60

# Storage key prefix for uploaded media.
STORAGE_PREFIX = "media"
