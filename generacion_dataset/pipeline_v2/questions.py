"""Validación común de preguntas generadas (pasos 02 y 03) y carga de prompts."""
from __future__ import annotations

import re
from pathlib import Path

import config
from common import content_tokens, jaccard, lexical_overlap

PROMPTS = Path(__file__).parent / "prompts"
_NORM_CITE = re.compile(r"(?i)\b(art[ií]culo|art\.)\s*\d|\bley\s*(n[°º.]?\s*)?\d|\bd\.?\s*leg|\bd\.?\s*s\.?\s*n|\bcasaci[oó]n\s*\d|\bexp(ediente)?\.?\s*n")


def load_prompt(name: str, **subs: object) -> str:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    base = {"TOPICS": ", ".join(config.TOPICS), "BARRIERS": ", ".join(config.BARRIERS)}
    for k, v in {**base, **{k: str(v) for k, v in subs.items()}}.items():
        text = text.replace(f"<<{k}>>", str(v))
    return text


class Deduper:
    """Rechaza preguntas casi idénticas (Jaccard de palabras de contenido) respecto de las ya aceptadas."""

    def __init__(self, threshold: float = config.NEAR_DUP_JACCARD):
        self.threshold, self.sets = threshold, []

    def seen(self, query: str) -> bool:
        t = frozenset(content_tokens(query))
        return any(len(t & s) / max(1, len(t | s)) >= self.threshold for s in self.sets)

    def add(self, query: str) -> None:
        self.sets.append(frozenset(content_tokens(query)))


def check_question(raw: dict, positive_texts: list[str], dedupe: Deduper, max_overlap: float) -> tuple[dict | None, str]:
    """Devuelve (pregunta limpia, '') o (None, motivo_de_rechazo)."""
    q = str(raw.get("query") or "").strip()
    if not (config.QUERY_MIN_CHARS <= len(q) <= config.QUERY_MAX_CHARS):
        return None, "largo_fuera_de_rango"
    if _NORM_CITE.search(q):
        return None, "cita_norma"
    ov = max((lexical_overlap(q, t) for t in positive_texts), default=0.0)
    if ov > max_overlap:
        return None, "solapamiento_alto"
    if dedupe.seen(q):
        return None, "duplicada"
    topic = raw.get("topic") if raw.get("topic") in config.TOPICS else "otro"
    barrier = raw.get("barrier") if raw.get("barrier") in config.BARRIERS else "otro"
    dedupe.add(q)
    return {"query": q, "topic": topic, "barrier": barrier, "lexical_overlap": round(ov, 3),
            "expected_answer_focus": str(raw.get("expected_answer_focus") or "").strip()}, ""
