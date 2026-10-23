#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from legal_data.config import get_settings
from legal_data.json_utils import extract_json_object
from legal_data.llm_prompts import PDF_CLASSIFY_AND_EXTRACT_PROMPT
from legal_data.openrouter_client import build_openrouter_client
from legal_data.pdf_images import combine_pairs, image_to_png_bytes, pdf_bytes_to_images, save_combined_images


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: uv run python scripts/classify_pdf_with_llm.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    pdf_bytes = pdf_path.read_bytes()
    images = pdf_bytes_to_images(pdf_bytes)
    combined = combine_pairs(images)

    out_dir = pdf_path.parent / "images"
    save_combined_images(combined, out_dir)

    client = build_openrouter_client()
    settings = get_settings()

    content = [{"type": "text", "text": PDF_CLASSIFY_AND_EXTRACT_PROMPT}]
    for image in combined:
        png_bytes = image_to_png_bytes(image)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[{"role": "user", "content": content}],
    )

    text = response.choices[0].message.content or "{}"
    data = extract_json_object(text)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
