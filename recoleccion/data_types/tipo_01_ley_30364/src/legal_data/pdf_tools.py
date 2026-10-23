from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader


def extract_text_with_pdftotext(pdf_bytes: bytes) -> str:
    """Extrae texto con `pdftotext` si está disponible en el sistema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "input.pdf"
        txt_path = Path(tmpdir) / "output.txt"
        pdf_path.write_bytes(pdf_bytes)
        result = subprocess.run(
            ["pdftotext", str(pdf_path), str(txt_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pdftotext falló con código {result.returncode}: {result.stderr.strip()}"
            )
        return txt_path.read_text(encoding="utf-8", errors="replace")


def extract_text_with_pypdf(pdf_bytes: bytes) -> str:
    """Fallback Python puro cuando no existe pdftotext en el host."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    """Intenta primero con pdftotext y luego cae a pypdf."""
    if shutil.which("pdftotext"):
        return extract_text_with_pdftotext(pdf_bytes), "pdftotext"
    return extract_text_with_pypdf(pdf_bytes), "pypdf"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def mentions_law_30364(text: str) -> bool:
    compact = normalize_whitespace(text).lower()
    patterns = [
        "ley n° 30364",
        "ley nº 30364",
        "ley no 30364",
        "ley 30364",
    ]
    return any(p in compact for p in patterns)
