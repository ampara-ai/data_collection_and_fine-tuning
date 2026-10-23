#!/usr/bin/env python3
"""Descarga de muestra de un PDF expuesto por El Peruano.

No intenta aún hacer OCR ni parsing del contenido.
Solo verifica que la URL entregada por GraphQL sea descargable.
"""

from __future__ import annotations

import pathlib
import sys

import requests


def download(url: str, output_path: str) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    pathlib.Path(output_path).write_bytes(response.content)
    print(f"Descargado: {output_path} ({len(response.content)} bytes)")


def main() -> None:
    if len(sys.argv) < 3:
        print("Uso: python3 scripts/download_pdf_sample.py <url_pdf> <output_path>")
        sys.exit(1)
    download(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
