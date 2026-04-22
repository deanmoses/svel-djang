"""Image processing: validation, format conversion, and rendition generation.

Pure library code — no Django imports, no storage, no models.
Adapted from flipfix's core/image_processing.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from apps.media.constants import (
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
    WEB_NATIVE_FORMATS,
    WEBP_FORMAT,
    ImageFormat,
)


class InvalidImageError(ValueError):
    """Raised when image data cannot be decoded or fails validation."""


@dataclass(frozen=True, slots=True)
class ImageInfo:
    """Result of validate_image()."""

    width: int
    height: int
    pillow_format: str  # e.g. "JPEG", "PNG", "WEBP"
    mode: str  # e.g. "RGB", "RGBA", "L"


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    """Result of process_original() and generate_rendition()."""

    data: bytes
    mime_type: str
    width: int
    height: int
    format_ext: str  # e.g. "jpg", "png", "webp"


def _choose_original_format(pillow_format: str | None, mode: str) -> str:
    """Decide the output format for the original rendition."""
    # PNG with transparency stays PNG.
    if pillow_format == "PNG" and mode in ("RGBA", "LA"):
        return "PNG"
    # Web-native formats are preserved.
    if pillow_format in WEB_NATIVE_FORMATS:
        return pillow_format
    # Everything else (HEIC, GIF, BMP, etc.) -> JPEG.
    return "JPEG"


def _encode(image: Image.Image, fmt: ImageFormat) -> ProcessedImage:
    """Encode a PIL Image to bytes using the given format settings."""
    buf = BytesIO()
    save_kwargs: dict = {"format": fmt.extension.upper()}
    # Pillow uses "JPEG" not "JPG".
    if save_kwargs["format"] == "JPG":
        save_kwargs["format"] = "JPEG"
    if fmt.quality is not None:
        save_kwargs["quality"] = fmt.quality
    if fmt.optimize:
        save_kwargs["optimize"] = True
    image.save(buf, **save_kwargs)
    return ProcessedImage(
        data=buf.getvalue(),
        mime_type=fmt.content_type,
        width=image.size[0],
        height=image.size[1],
        format_ext=fmt.extension,
    )


def validate_image(data: bytes) -> ImageInfo:
    """Validate image data and return metadata.

    Opens with Pillow and forces a full decode. Rejects degenerate
    dimensions (< MIN_IMAGE_DIMENSION or > MAX_IMAGE_DIMENSION).
    Does NOT enforce the extension allowlist — that is the upload
    endpoint's responsibility (Phase 3).

    Raises InvalidImageError on any failure.
    """
    if not data:
        raise InvalidImageError("Empty image data.")

    try:
        image = Image.open(BytesIO(data))
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Cannot identify image file.") from exc
    except Exception as exc:
        raise InvalidImageError(f"Cannot decode image: {exc}") from exc

    # Check dimensions from header BEFORE .load() to avoid allocating
    # memory for oversized images.
    width, height = image.size
    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        raise InvalidImageError(
            f"Image too small ({width}x{height}). "
            f"Minimum dimension is {MIN_IMAGE_DIMENSION}px."
        )
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise InvalidImageError(
            f"Image too large ({width}x{height}). "
            f"Maximum dimension is {MAX_IMAGE_DIMENSION}px."
        )

    try:
        image.load()  # Force full pixel decode to catch corrupt data.
    except Exception as exc:
        raise InvalidImageError(f"Cannot decode image: {exc}") from exc

    return ImageInfo(
        width=width,
        height=height,
        pillow_format=image.format or "UNKNOWN",
        mode=image.mode,
    )


def process_original(data: bytes) -> ProcessedImage:
    """Prepare the original rendition. Always re-encodes.

    - EXIF orientation correction (strips EXIF data for privacy).
    - Format conversion per the accepted-format table:
      PNG with alpha -> PNG, web-native -> same format,
      everything else (HEIC, GIF, BMP, etc.) -> JPEG.
    - GIF: silently takes first frame.
    - No resize.
    """
    image = Image.open(BytesIO(data))
    original_format = image.format

    # EXIF orientation correction (also strips EXIF).
    transposed = ImageOps.exif_transpose(image)
    if transposed is not None:
        image = transposed

    # Determine target format.
    target_format = _choose_original_format(original_format, image.mode)
    fmt = WEB_NATIVE_FORMATS[target_format]

    # Mode conversion for JPEG (can't store alpha).
    if target_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    return _encode(image, fmt)


def generate_rendition(data: bytes, max_dimension: int) -> ProcessedImage:
    """Generate a WebP rendition at the given max dimension.

    - EXIF orientation correction.
    - Resize via LANCZOS resampling (no upscale).
    - Always outputs WebP.
    """
    image = Image.open(BytesIO(data))

    # EXIF orientation correction.
    transposed = ImageOps.exif_transpose(image)
    if transposed is not None:
        image = transposed

    # Downscale only — don't upscale small images.
    if image.size[0] > max_dimension or image.size[1] > max_dimension:
        image = ImageOps.contain(
            image, (max_dimension, max_dimension), Image.Resampling.LANCZOS
        )

    # WebP only supports RGB/RGBA. Convert other modes (CMYK, P, LA, etc.).
    if image.mode == "RGBA":
        pass  # Keep alpha.
    elif image.mode != "RGB":
        image = image.convert("RGB")

    return _encode(image, WEBP_FORMAT)


def check_codec_support() -> dict[str, bool]:
    """Check availability of optional image codecs.

    Returns a dict mapping extension names to availability.
    Phase 3's upload endpoint uses this to return specific
    'format not supported' errors instead of generic decode failures.
    """
    heif_ok = False
    try:
        from pillow_heif import HeifImagePlugin  # noqa: F401

        heif_ok = True
    except ImportError:
        pass
    from PIL import features

    avif_ok = bool(features.check("avif"))
    return {"heic": heif_ok, "heif": heif_ok, "avif": avif_ok}
