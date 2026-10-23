#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

INDEX_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_index_llm_sample.json")
CASE_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_case_detail_llm_sample.json")
OUTPUT_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/case_context_units_sample.json")


def norm_code_from_page_id(page_id: str) -> str:
    mapping = {
        "jp_0086": "CPP",
        "jp_0217": "CPP",
        "jp_0050": "CPP",
        "jp_0003": "CP",
        "jp_0005": "CP",
    }
    return mapping.get(page_id, "UNKNOWN")


def article_id_from_index(parsed: dict) -> str | None:
    if "article" in parsed:
        article = str(parsed["article"])
        if article.startswith("Artículo "):
            return article.split(".")[0].replace("Artículo ", "").strip()
        return article
    if "articulo" in parsed:
        return str(parsed["articulo"])
    return None


def article_heading_from_index(parsed: dict) -> str | None:
    if "article" in parsed:
        return parsed["article"]
    if "articulo" in parsed:
        return f"Artículo {parsed['articulo']}"
    return None


def concordances_from_index(parsed: dict) -> list[dict]:
    raw = parsed.get("concordancias", {})
    out = []
    for code, refs in raw.items():
        parts = [x.strip() for x in str(refs).replace("arts.", "").replace("art.", "").split(",") if x.strip()]
        for part in parts:
            out.append({
                "code": code,
                "article_id": part,
                "relation_type": "concordance",
                "confidence": "high",
            })
    return out


def find_source_trace(index_data: list, case_url: str) -> tuple[str | None, dict | None, str | None]:
    for page in index_data:
        parsed = page["parsed"]
        categories = parsed.get("categories") or parsed.get("categorias") or []
        for cat in categories:
            cat_name = cat.get("name") or cat.get("nombre")
            for entry in cat.get("entries", []):
                matched = entry.get("matched_url")
                if matched == case_url:
                    return page["page_id"], parsed, cat_name
    return None, None, None


def build_unit(i: int, index_data: list, case_item: dict) -> dict:
    url = case_item["url"]
    parsed_case = case_item["parsed"]
    page_id, index_parsed, category = find_source_trace(index_data, url)

    anchor_code = norm_code_from_page_id(page_id) if page_id else "UNKNOWN"
    anchor_article_id = article_id_from_index(index_parsed) if index_parsed else None
    anchor_heading = article_heading_from_index(index_parsed) if index_parsed else None

    title = (
        parsed_case.get("titulo")
        or parsed_case.get("title")
        or parsed_case.get("tema")
        or parsed_case.get("sumilla")
        or ""
    )
    resolution_reference = (
        parsed_case.get("numero_expediente")
        or parsed_case.get("resolution_reference")
        or parsed_case.get("identificacion", {}).get("numero")
    )
    court = parsed_case.get("court") or parsed_case.get("corte") or parsed_case.get("identificacion", {}).get("corte")
    chamber = parsed_case.get("chamber") or parsed_case.get("sala") or parsed_case.get("identificacion", {}).get("sala")
    date_text = parsed_case.get("fecha") or parsed_case.get("date_text") or parsed_case.get("identificacion", {}).get("fecha")
    judge = parsed_case.get("ponente") or parsed_case.get("judge_rapporteur") or parsed_case.get("identificacion", {}).get("ponente")
    sumilla = parsed_case.get("sumilla")
    highlighted = parsed_case.get("fundamento_destacado")
    if not highlighted:
        fundamentos = parsed_case.get("fundamentos_destacados")
        if isinstance(fundamentos, list) and fundamentos:
            highlighted = fundamentos[0].get("texto")
    facts_background = parsed_case.get("facts_or_background")
    if not facts_background:
        facts_background = parsed_case.get("antecedentes") or parsed_case.get("fundamentos_de_hecho") or None
    legal_issue = parsed_case.get("legal_issue")
    reasoning = None
    if isinstance(parsed_case.get("fundamentos_destacados"), list):
        reasoning = " ".join(x.get("texto", "") for x in parsed_case["fundamentos_destacados"][:3]).strip() or None
    decision_summary = parsed_case.get("resolucion")
    pdf_url = parsed_case.get("pdf_url") or parsed_case.get("urls", {}).get("pdf")

    unit = {
        "unit_id": f"case_ctx_{i:06d}",
        "source_type": "jurisprudencia",
        "source_trace": {
            "index_page_id": page_id,
            "index_page_url": None,
            "entry_category": category,
            "entry_title_raw": title,
            "entry_url": url,
            "pdf_url": pdf_url,
            "resolution_reference_raw": resolution_reference,
        },
        "case_record": {
            "title": title,
            "resolution_reference": resolution_reference,
            "resolution_type": parsed_case.get("tipo_resolucion") or None,
            "court": court,
            "chamber": chamber,
            "date_text": date_text,
            "judge_rapporteur": judge,
            "topic_label": parsed_case.get("tema") or title,
            "sumilla": sumilla,
            "highlighted_holding": highlighted,
            "facts_background": facts_background,
            "legal_issue": legal_issue,
            "reasoning_summary": reasoning,
            "decision_summary": decision_summary,
            "participants": {
                "victim_or_claimant": parsed_case.get("agraviados"),
                "accused_or_investigated": None,
                "third_parties": [parsed_case["tercero_civil"]] if parsed_case.get("tercero_civil") else [],
            },
        },
        "legal_context": {
            "anchor_norm": {
                "code": anchor_code,
                "article_id": anchor_article_id,
                "heading": anchor_heading,
                "relation_type": "anchor",
                "confidence": "high",
            },
            "explicit_concordances": concordances_from_index(index_parsed) if index_parsed else [],
            "inferred_related_norms": [],
            "institutional_context": [],
        },
        "dataset_signals": {
            "domain_relevance": {
                "violencia_familiar": "unknown",
                "violencia_genero": "unknown",
                "proteccion_victima": "unknown",
                "procedural_guidance": "medium" if anchor_code == "CPP" else "low",
            },
            "query_generation_ready": bool(sumilla or facts_background or highlighted),
            "query_generation_source": "facts_background" if facts_background else "sumilla",
            "positive_context_ready": True,
            "positive_context_strategy": "case_plus_anchor_norm",
            "hard_negative_group_keys": [x for x in [anchor_code, anchor_article_id, category] if x],
            "needs_human_review": False,
            "notes_for_generation": "Muestra inicial transformada desde extracción LLM de índice y detalle de resolución.",
        },
    }
    return unit


def main() -> None:
    index_data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    case_data = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    units = [build_unit(i + 1, index_data, item) for i, item in enumerate(case_data)]
    OUTPUT_PATH.write_text(json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"units": len(units), "output_path": str(OUTPUT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
