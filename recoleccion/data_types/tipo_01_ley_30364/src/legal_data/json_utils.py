from __future__ import annotations

import json


def extract_json_object(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No se encontró JSON válido en la respuesta del modelo")
    return json.loads(text[start:end + 1])
