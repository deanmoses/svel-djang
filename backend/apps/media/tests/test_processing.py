"""Tests for the image processing module (Phase 2).

Pure unit tests — no database, no Django models, no storage.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from apps.media.processing import (
    ImageInfo,
    InvalidImageError,
    ProcessedImage,
    check_codec_support,
    generate_rendition,
    process_original,
    validate_image,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

# Minimal valid 1x1 RGBA PNG (for tests that just need valid image bytes).
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_test_image(
    width: int = 100,
    height: int = 100,
    fmt: str = "PNG",
    mode: str = "RGB",
    color: str = "red",
) -> bytes:
    """Create test image bytes in the given format."""
    image = Image.new(mode, (width, height), color=color)
    buf = BytesIO()
    save_kwargs: dict[str, Any] = {"format": fmt}
    if fmt == "JPEG" and mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(buf, **save_kwargs)
    return buf.getvalue()


def create_exif_rotated_jpeg(width: int = 200, height: int = 100) -> bytes:
    """Create a JPEG with EXIF orientation tag 6 (90 CW rotation).

    The stored pixels are width x height, but orientation says the
    displayed image should be height x width.
    """
    import struct

    image = Image.new("RGB", (width, height), color="blue")
    buf = BytesIO()
    image.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    # Build a minimal EXIF segment with orientation = 6 (90 CW).
    # EXIF structure: APP1 marker + Tiff header + IFD with orientation tag.
    byte_order = b"MM"  # big-endian
    tiff_header = byte_order + b"\x00\x2a" + struct.pack(">I", 8)
    # IFD: 1 entry
    ifd_count = struct.pack(">H", 1)
    # Tag 0x0112 (Orientation), type SHORT (3), count 1, value 6
    ifd_entry = struct.pack(">HHI", 0x0112, 3, 1) + struct.pack(">HH", 6, 0)
    # Next IFD offset = 0 (no more IFDs)
    ifd_next = struct.pack(">I", 0)
    exif_body = tiff_header + ifd_count + ifd_entry + ifd_next
    exif_segment = (
        b"\xff\xe1"
        + struct.pack(">H", len(exif_body) + 8)
        + b"Exif\x00\x00"
        + exif_body
    )

    # Insert EXIF after SOI marker (first 2 bytes).
    return jpeg_bytes[:2] + exif_segment + jpeg_bytes[2:]


def _can_encode(fmt: str) -> bool:
    """Check if Pillow can encode the given format."""
    return fmt in Image.SAVE


# ---------------------------------------------------------------------------
# validate_image
# ---------------------------------------------------------------------------


class TestValidateImage:
    def test_valid_png(self):
        data = create_test_image(50, 50, fmt="PNG")
        info = validate_image(data)
        assert isinstance(info, ImageInfo)
        assert info.width == 50
        assert info.height == 50
        assert info.pillow_format == "PNG"
        assert info.mode == "RGB"

    def test_valid_jpeg(self):
        data = create_test_image(80, 60, fmt="JPEG")
        info = validate_image(data)
        assert info.width == 80
        assert info.height == 60
        assert info.pillow_format == "JPEG"

    def test_valid_rgba_png(self):
        data = create_test_image(10, 10, fmt="PNG", mode="RGBA")
        info = validate_image(data)
        assert info.mode == "RGBA"

    def test_corrupt_bytes(self):
        with pytest.raises(InvalidImageError):
            validate_image(b"not an image at all")

    def test_empty_bytes(self):
        with pytest.raises(InvalidImageError):
            validate_image(b"")

    def test_too_small_1x1(self):
        """1x1 is below MIN_IMAGE_DIMENSION (2)."""
        with pytest.raises(InvalidImageError):
            validate_image(MINIMAL_PNG)

    def test_too_large_dimension(self):
        """One dimension exceeds MAX_IMAGE_DIMENSION."""
        # Create a narrow but very tall image header. We use BMP because
        # Pillow reads BMP dimensions without decoding all pixels.
        data = create_test_image(2, 30000, fmt="BMP")
        with pytest.raises(InvalidImageError):
            validate_image(data)

    def test_boundary_2x2_passes(self):
        data = create_test_image(2, 2, fmt="PNG")
        info = validate_image(data)
        assert info.width == 2
        assert info.height == 2


# ---------------------------------------------------------------------------
# process_original
# ---------------------------------------------------------------------------


class TestProcessOriginal:
    def test_jpeg_preserved(self):
        data = create_test_image(100, 100, fmt="JPEG")
        result = process_original(data)
        assert isinstance(result, ProcessedImage)
        assert result.format_ext == "jpg"
        assert result.mime_type == "image/jpeg"
        assert result.width == 100
        assert result.height == 100

    def test_png_preserved(self):
        data = create_test_image(100, 100, fmt="PNG")
        result = process_original(data)
        assert result.format_ext == "png"
        assert result.mime_type == "image/png"

    def test_webp_preserved(self):
        data = create_test_image(100, 100, fmt="WEBP")
        result = process_original(data)
        assert result.format_ext == "webp"
        assert result.mime_type == "image/webp"

    @pytest.mark.skipif(not _can_encode("AVIF"), reason="AVIF codec unavailable")
    def test_avif_preserved(self):
        data = create_test_image(100, 100, fmt="AVIF")
        result = process_original(data)
        assert result.format_ext == "avif"
        assert result.mime_type == "image/avif"

    def test_bmp_converted_to_jpeg(self):
        data = create_test_image(100, 100, fmt="BMP")
        result = process_original(data)
        assert result.format_ext == "jpg"
        assert result.mime_type == "image/jpeg"

    def test_gif_converted_to_jpeg(self):
        data = create_test_image(100, 100, fmt="GIF")
        result = process_original(data)
        assert result.format_ext == "jpg"
        assert result.mime_type == "image/jpeg"

    def test_rgba_png_stays_png(self):
        data = create_test_image(100, 100, fmt="PNG", mode="RGBA")
        result = process_original(data)
        assert result.format_ext == "png"
        assert result.mime_type == "image/png"

    def test_rgba_png_preserves_alpha(self):
        data = create_test_image(100, 100, fmt="PNG", mode="RGBA")
        result = process_original(data)
        img = Image.open(BytesIO(result.data))
        assert img.mode in ("RGBA", "LA")

    def test_no_resize(self):
        """process_original does not resize — dimensions match input."""
        data = create_test_image(3000, 2000, fmt="JPEG")
        result = process_original(data)
        assert result.width == 3000
        assert result.height == 2000

    def test_exif_orientation_corrected(self):
        """EXIF rotation tag is applied — output dimensions are transposed."""
        # Input pixels are 200x100, but EXIF says 90 CW -> displayed 100x200.
        data = create_exif_rotated_jpeg(200, 100)
        result = process_original(data)
        assert result.width == 100
        assert result.height == 200

    def test_output_is_valid_image(self):
        data = create_test_image(100, 100, fmt="JPEG")
        result = process_original(data)
        img = Image.open(BytesIO(result.data))
        img.load()  # force decode — should not raise
        assert img.size == (100, 100)

    def test_heic_converted_to_jpeg(self):
        """HEIC -> JPEG (skip if pillow-heif unavailable)."""
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError:
            pytest.skip("pillow-heif not available")

        # Create a HEIF image via pillow-heif.
        try:
            img = Image.new("RGB", (100, 100), color="green")
            buf = BytesIO()
            img.save(buf, format="HEIF")
            data = buf.getvalue()
        except KeyError, OSError:
            pytest.skip("HEIF encoding not supported in this environment")

        result = process_original(data)
        assert result.format_ext == "jpg"
        assert result.mime_type == "image/jpeg"


# ---------------------------------------------------------------------------
# generate_rendition
# ---------------------------------------------------------------------------


class TestGenerateRendition:
    def test_large_image_downsized(self):
        data = create_test_image(1600, 800, fmt="JPEG")
        result = generate_rendition(data, max_dimension=400)
        assert result.width == 400
        assert result.height == 200

    def test_small_image_not_upscaled(self):
        data = create_test_image(100, 80, fmt="JPEG")
        result = generate_rendition(data, max_dimension=400)
        assert result.width == 100
        assert result.height == 80

    def test_aspect_ratio_preserved(self):
        data = create_test_image(1600, 800, fmt="PNG")
        result = generate_rendition(data, max_dimension=400)
        assert result.width == 400
        assert result.height == 200

    def test_always_webp(self):
        for fmt in ("JPEG", "PNG"):
            data = create_test_image(200, 200, fmt=fmt)
            result = generate_rendition(data, max_dimension=400)
            assert result.format_ext == "webp"
            assert result.mime_type == "image/webp"

    def test_rgba_input_produces_webp(self):
        data = create_test_image(200, 200, fmt="PNG", mode="RGBA")
        result = generate_rendition(data, max_dimension=400)
        assert result.format_ext == "webp"
        assert result.mime_type == "image/webp"

    def test_exif_orientation_applied(self):
        """EXIF rotation is applied before resize."""
        # Stored 200x100, EXIF says 90 CW -> logical 100x200.
        # max_dimension=100 should keep it at 100x200 (already fits)
        # but if orientation wasn't applied, it would be 100x50.
        data = create_exif_rotated_jpeg(200, 100)
        result = generate_rendition(data, max_dimension=100)
        # After EXIF: 100x200. Fit to 100: 50x100.
        assert result.height == 100
        assert result.width == 50

    def test_cmyk_input_produces_webp(self):
        """CMYK JPEG (print workflow) is converted to RGB for WebP."""
        img = Image.new("CMYK", (200, 200), color=(0, 0, 0, 255))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()
        result = generate_rendition(data, max_dimension=100)
        assert result.format_ext == "webp"
        output = Image.open(BytesIO(result.data))
        assert output.mode == "RGB"

    def test_output_is_valid_image(self):
        data = create_test_image(500, 500, fmt="JPEG")
        result = generate_rendition(data, max_dimension=200)
        img = Image.open(BytesIO(result.data))
        img.load()
        assert img.size == (200, 200)
        assert img.format == "WEBP"


# ---------------------------------------------------------------------------
# check_codec_support
# ---------------------------------------------------------------------------


class TestCheckCodecSupport:
    def test_returns_dict(self):
        result = check_codec_support()
        assert isinstance(result, dict)
        assert "heic" in result
        assert "heif" in result
        assert "avif" in result

    def test_values_are_bool(self):
        result = check_codec_support()
        for value in result.values():
            assert isinstance(value, bool)
