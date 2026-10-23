from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

from pdf2image import convert_from_bytes
from PIL import Image


def pdf_bytes_to_images(pdf_bytes: bytes, dpi: int = 150):
    return convert_from_bytes(pdf_bytes, dpi=dpi)


def combine_pairs(images: list[Image.Image]) -> list[Image.Image]:
    combined: list[Image.Image] = []
    for idx in range(0, len(images), 2):
        chunk = images[idx: idx + 2]
        widths = [img.width for img in chunk]
        heights = [img.height for img in chunk]
        canvas = Image.new("RGB", (max(widths), sum(heights)), color="white")
        y = 0
        for img in chunk:
            canvas.paste(img, (0, y))
            y += img.height
        combined.append(canvas)
    return combined


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def save_combined_images(images: list[Image.Image], out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, image in enumerate(images, start=1):
        path = out / f"pages_{i:03d}.png"
        image.save(path, format="PNG")
        paths.append(path)
    return paths
