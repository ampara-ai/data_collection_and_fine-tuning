#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

INPUT_URL = "https://lpderecho.pe/acuerdo-plenario-5-2016-cij-116-delitos-violencia-mujer-integrantes-grupo-familiar-ambito-procesal-ley-30364/"
OUTPUT_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/violencia_familiar_case_v2_sample.json")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_clean_case_payload(url: str) -> dict[str, Any]:
    import requests

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    content = soup.select_one("div.td-post-content")
    if not content:
        raise RuntimeError("td-post-content not found")

    lines = []
    pdf_url = None
    for tag in content.find_all(["h2", "h3", "h4", "p", "strong", "a", "li"], limit=260):
        txt = normalize_text(tag.get_text(" ", strip=True))
        if not txt:
            continue
        if any(noise in txt.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado"]):
            continue
        if tag.name == "a":
            href = tag.get("href")
            if href and href.endswith(".pdf"):
                pdf_url = href
            continue
        lines.append(f"[{tag.name}] {txt}")

    title_tag = soup.select_one("h1")
    page_title = normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else None

    return {
        "url": url,
        "page_title": page_title,
        "pdf_url_detected": pdf_url,
        "clean_text": "\n".join(lines),
    }


def main() -> None:
    load_dotenv()
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    model = os.environ.get("OPENROUTER_MODEL", "x-ai/grok-4.1-fast")

    payload = fetch_clean_case_payload(INPUT_URL)
    schema_hint = {
        "unit_id": "case_ctx_vf_000001",
        "source_type": "jurisprudencia",
        "source_trace": {
            "index_page_id": None,
            "index_page_url": None,
            "entry_category": None,
            "entry_title_raw": None,
            "entry_url": INPUT_URL,
            "pdf_url": None,
            "resolution_reference_raw": None,
        },
        "case_record": {
            "title": None,
            "resolution_reference": None,
            "resolution_type": None,
            "court": None,
            "chamber": None,
            "date_text": None,
            "judge_rapporteur": None,
            "topic_label": None,
            "sumilla": None,
            "highlighted_holding": None,
            "facts_background": None,
            "legal_issue": None,
            "reasoning_summary": None,
            "decision_summary": None,
            "participants": {
                "victim_or_claimant": None,
                "accused_or_investigated": None,
                "third_parties": []
            }
        },
        "legal_context": {
            "anchor_norm": {
                "code": "Ley30364",
                "article_id": None,
                "heading": None,
                "relation_type": "anchor",
                "confidence": "medium"
            },
            "explicit_concordances": [],
            "explicit_norms_mentioned_in_case": [],
            "inferred_related_norms": [],
            "institutional_context": []
        },
        "domain_mapping": {
            "relevance_label": None,
            "relevance_score": None,
            "relevance_rationale": None,
            "violence_family_link_type": None,
            "can_generate_domain_case": None,
            "domain_case_generation_mode": None,
            "forbidden_generation_reason": None
        },
        "dataset_generation": {
            "query_generation_ready": None,
            "query_generation_source": None,
            "positive_context_ready": None,
            "positive_context_strategy": None,
            "hard_negative_group_keys": [],
            "synthetic_case_allowed": None,
            "synthetic_case_constraints": [],
            "synthetic_case_outline": {
                "user_situation": None,
                "legal_need": None,
                "why_this_case_is_relevant": None
            },
            "needs_human_review": None
        }
    }

    system_prompt = (
        "Eres un extractor jurídico peruano especializado en jurisprudencia y dataset construction. "
        "Responde SOLO en JSON válido. No inventes hechos, artículos ni citas específicas. "
        "Distingue siempre entre normas explícitamente mencionadas y normas solo inferidas. "
        "La jurisdicción es Perú. Si no estás seguro, usa null, lista vacía o confidence baja."
    )
    user_prompt = (
        "Extrae esta publicación de LP Derecho al schema v2 de case_context_unit. "
        "Tu prioridad es mapear bien el contexto relevante para violencia familiar, violencia contra la mujer, "
        "protección de víctimas y ámbito procesal peruano.\n\n"
        "Reglas:\n"
        "1. Usa SOLO derecho peruano.\n"
        "2. No inventes artículos específicos si el texto no los sustenta.\n"
        "3. Si la jurisprudencia es directamente relevante al dominio, márcala como direct.\n"
        "4. synthetic_case_allowed solo debe ser true si la adaptación a un caso cotidiano de violencia familiar es jurídicamente defendible.\n"
        "5. En explicit_norms_mentioned_in_case incluye leyes, artículos o cuerpos normativos citados de forma visible.\n"
        "6. En inferred_related_norms solo incluye normas peruanas razonablemente relacionadas y explica por qué.\n\n"
        f"SCHEMA OBJETIVO:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        extra_headers={
            "HTTP-Referer": "https://openclaw.local",
            "X-Title": os.environ.get("APP_NAME", "peru-legal-rag-data"),
        },
    )

    if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
        raise RuntimeError(f"empty model response: {response}")

    parsed = json.loads(response.choices[0].message.content)
    OUTPUT_PATH.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(OUTPUT_PATH), "url": INPUT_URL}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
