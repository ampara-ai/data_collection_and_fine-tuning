from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from legal_candidate_resolver import (
    LegalCandidateResolver,
    RESOLVER_VERSION,
    ResolutionResult,
    candidates_for_prompt,
    portable_path,
    validate_positive_candidate_ids,
)


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent

DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "input" / "document_chunks_all.jsonl"
DEFAULT_CASES_DIR = PROJECT_ROOT / "data" / "intermediate" / "resumeai_batch" / "cases"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "legal_questions_dataset"
DEFAULT_UPDATES_PATH = PROJECT_ROOT / "data" / "intermediate" / "jurisprudencia_chunk_updates.jsonl"
DEFAULT_CONTEXT_UNITS_PATH = PROJECT_ROOT / "data" / "input" / "jurisprudence_context_units.json"
DEFAULT_CP_ARTICLES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_02_codigo_penal" / "data" / "processed" / "all_articles.json"
DEFAULT_CPP_ARTICLES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "all_articles.json"
DEFAULT_LEY_30364_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_01_ley_30364" / "data" / "processed" / "law_30364_structured.json"
DEFAULT_STRUCTURED_ENTRIES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_04_jurisprudencia" / "data" / "processed" / "jurisprudence_entries_structured.json"

MODEL_NAME = "anthropic/claude-sonnet-5.5"
MODEL_TEMPERATURE = 0.3
PROMPT_VERSION = "closed-positive-and-negative-candidates-v3"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_NEGATIVE_POOL_SIZE = 20


# ============================================================
# 2. SCHEMA DEL LLM
# ============================================================

BarrierType = Literal[
    "verguenza",
    "desconocimiento_derechos",
    "no_sabe_como_denunciar",
    "desconfianza_sistema",
    "miedo_agresor",
    "dependencia_economica",
    "preocupacion_hijos",
    "duda_si_es_delito",
    "otro",
]

QuestionTopic = Literal[
    "identificacion_delito",
    "canales_denuncia",
    "medidas_proteccion",
    "hijos_y_tenencia",
    "pruebas_y_certificados",
    "lesiones_secuelas_indemnizacion",
    "violencia_psicologica",
    "violencia_fisica",
    "violencia_economica",
    "violencia_sexual",
    "procedimiento_penal",
    "desconfianza_en_justicia",
    "reparacion_civil",
    "sancion_penal_al_agresor",
    "doctrina_jurisprudencial",
    "otro",
]


class GeneratedQuestion(BaseModel):
    query: str = Field(
        description=(
            "Pregunta coloquial que podría hacer una víctima de violencia familiar en Perú. "
            "Debe sonar natural, no técnica, y reflejar dudas, temor, vergüenza o desconfianza."
        )
    )
    normalized_query: str = Field(
        description="Versión corregida y más clara de la pregunta, manteniendo lenguaje ciudadano."
    )
    topic: QuestionTopic = Field(
        description="Tema principal de la pregunta."
    )
    barrier: BarrierType = Field(
        description="Barrera principal que explica por qué la persona no procede legalmente."
    )
    victim_voice_rationale: str = Field(
        description=(
            "Explicación breve de por qué esta pregunta es plausible para una víctima que duda "
            "en denunciar o proceder legalmente."
        )
    )
    positive_candidate_ids: list[str] = Field(
        min_length=1,
        description=(
            "Uno o más candidate_id copiados exactamente del conjunto cerrado de candidatos. "
            "Solo seleccionar documentos cuyo texto ayude directamente a responder la pregunta."
        )
    )
    positive_selection_reason: str = Field(
        description="Justificación breve y conjunta de por qué los documentos seleccionados responden la pregunta."
    )
    hard_negative_candidate_ids: list[str] = Field(
        min_length=1,
        max_length=10,
        description=(
            "IDs copiados exactamente de negative_candidate_documents. Deben ser documentos "
            "cercanos al tema, pero que no respondan ni ayuden materialmente a responder la pregunta."
        ),
    )
    hard_negative_selection_reason: str = Field(
        description=(
            "Explicación breve de por qué los negativos son plausibles para retrieval, pero no "
            "contienen la respuesta jurídica solicitada."
        )
    )
    expected_answer_focus: str = Field(
        description=(
            "Qué debería poder responder el sistema RAG usando los positivos. "
            "No responder la pregunta completa, solo indicar el foco esperado."
        )
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confianza del LLM en que la pregunta y las referencias son pertinentes.",
    )


class CaseQuestionBatch(BaseModel):
    case_id: str = Field(description="Identificador del caso, normalmente derivado del PDF o archivo JSON.")
    case_summary_for_traceability: str = Field(
        description="Resumen breve y no sensacionalista del caso usado como base."
    )
    jurisprudencia_chunk_text: str = Field(
        description=(
            "Síntesis en 3-5 oraciones del criterio jurídico principal que establece esta resolución. "
            "NO menciones nombres propios, fechas específicas, ni hechos particulares del caso. "
            "Expresa el principio o estándar jurídico general que se establece, la decisión adoptada "
            "y su relevancia para casos de violencia familiar en Perú. "
            "Usa lenguaje jurídico conciso, no coloquial. "
            "Este texto reemplazará al chunk en la base vectorial RAG."
        )
    )
    questions: list[GeneratedQuestion] = Field(
        min_length=1,
        max_length=12,
        description="Preguntas coloquiales generadas a partir del caso.",
    )


# ============================================================
# 3. UTILIDADES DE TEXTO
# ============================================================

def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9áéíóúñü\s\-\.]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    return [tok for tok in text.split() if len(tok) > 1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def pydantic_schema_text(model_class: type[BaseModel]) -> str:
    """
    Compatibilidad Pydantic v1/v2.
    """
    if hasattr(model_class, "model_json_schema"):
        return json.dumps(model_class.model_json_schema(), ensure_ascii=False, indent=2)
    return json.dumps(model_class.schema(), ensure_ascii=False, indent=2)


# ============================================================
# 4. LECTURA DE CHUNKS Y BM25
# ============================================================

def load_chunks(chunks_path: Path) -> list[dict[str, Any]]:
    chunks = []

    with chunks_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido en línea {line_number}: {exc}") from exc

            chunks.append(chunk)

    return chunks


def merge_corpus_chunks(
    snapshot_chunks: list[dict[str, Any]],
    complete_article_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sustituye artículos filtrados por sus textos completos y conserva el resto."""
    merged = {
        chunk.get("chunk_id"): chunk
        for chunk in snapshot_chunks
        if chunk.get("chunk_id")
    }
    for chunk in complete_article_chunks:
        merged[chunk["chunk_id"]] = chunk
    return list(merged.values())


def build_index_text(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    topic_tags = metadata.get("topic_tags") or chunk.get("retrieval_tags") or []

    title = chunk.get("title") or ""
    text = chunk.get("text") or ""
    tags = " ".join(str(tag) for tag in topic_tags)

    return f"{title}. {text} {tags}".strip()


def build_bm25(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Construye el índice en memoria para usar siempre el corpus cargado."""
    corpus_texts = [build_index_text(chunk) for chunk in chunks]
    tokenized_corpus = [tokenize(text) for text in corpus_texts]
    bm25 = BM25Okapi(tokenized_corpus)

    index = {
        "bm25": bm25,
        "chunks": chunks,
        "corpus_texts": corpus_texts,
        "tokenized_corpus": tokenized_corpus,
    }
    return index


def bm25_search(index: dict[str, Any], query: str, top_k: int = 8) -> list[dict[str, Any]]:
    bm25: BM25Okapi = index["bm25"]
    chunks: list[dict[str, Any]] = index["chunks"]

    scores = bm25.get_scores(tokenize(query))
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for rank, idx in enumerate(ranked_indices, start=1):
        chunk = chunks[idx]
        results.append(
            {
                "rank": rank,
                "score": float(scores[idx]),
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "source_type": chunk.get("source_type"),
                "title": chunk.get("title"),
                "article_id": (chunk.get("metadata") or {}).get("article_id"),
                "resolution_reference": (chunk.get("metadata") or {}).get("resolution_reference"),
            }
        )

    return results


# ============================================================
# 5. ÍNDICE DE JURISPRUDENCIA DEL CORPUS
# ============================================================


def normalize_article_id(article_id: str | None) -> str:
    if not article_id:
        return ""

    value = str(article_id).strip()

    value = value.replace("Artículo", "")
    value = value.replace("artículo", "")
    value = value.replace("Art.", "")
    value = value.replace("art.", "")
    value = value.replace("°", "")
    value = value.replace("º", "")

    value = re.sub(r"\s+", "", value)
    value = value.upper()

    return value


def normalize_resolution_reference(value: str | None) -> str:
    if not value:
        return ""

    value = str(value).strip().upper()

    value = value.replace("Nº", "")
    value = value.replace("N°", "")
    value = value.replace("NO.", "")
    value = value.replace("EXP.", "")
    value = value.replace("RN", "")
    value = value.replace("R.N.", "")

    value = re.sub(r"\s+", "", value)
    value = value.strip("[]()")

    return value


def build_lookup_indexes(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Índices determinísticos basados estrictamente en:

    - source_type
    - metadata.article_id
    - metadata.resolution_reference

    No inferimos tipos. Usamos lo que ya viene en document_chunks_all.jsonl.
    """

    by_source_article: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_resolution_reference: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_chunk_id: dict[str, dict[str, Any]] = {}
    by_source_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        source_type = chunk.get("source_type")
        metadata = chunk.get("metadata") or {}

        if chunk_id:
            by_chunk_id[chunk_id] = chunk

        if source_type:
            by_source_type[source_type].append(chunk)

        article_id = normalize_article_id(metadata.get("article_id"))
        if source_type and article_id:
            by_source_article[(source_type, article_id)].append(chunk)

        resolution_reference = normalize_resolution_reference(
            metadata.get("resolution_reference")
        )
        if source_type == "tipo_04_jurisprudencia" and resolution_reference:
            by_resolution_reference[resolution_reference].append(chunk)

    return {
        "by_source_article": by_source_article,
        "by_resolution_reference": by_resolution_reference,
        "by_chunk_id": by_chunk_id,
        "by_source_type": by_source_type,
    }

def resolve_case_jurisprudence(
    case_data: dict[str, Any],
    lookup: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Busca el chunk tipo_04_jurisprudencia usando la resolución del JSON resumido.

    Fuente:
    - source_trace.resolution_reference_raw
    - resumeai_run.resolution_reference_raw

    Match contra:
    - chunk["source_type"] == "tipo_04_jurisprudencia"
    - chunk["metadata"]["resolution_reference"]
    """

    source_trace = case_data.get("source_trace") or {}
    resumeai_run = case_data.get("resumeai_run") or {}

    raw_resolution = (
        source_trace.get("resolution_reference_raw")
        or resumeai_run.get("resolution_reference_raw")
        or ""
    )

    normalized_resolution = normalize_resolution_reference(raw_resolution)

    if not normalized_resolution:
        return [], {
            "raw_resolution_reference": raw_resolution,
            "normalized_resolution_reference": normalized_resolution,
            "status": "missing_resolution_reference",
        }

    chunks = lookup["by_resolution_reference"].get(normalized_resolution, [])

    if not chunks:
        return [], {
            "raw_resolution_reference": raw_resolution,
            "normalized_resolution_reference": normalized_resolution,
            "status": "not_found_in_document_chunks",
        }

    return chunks, {
        "raw_resolution_reference": raw_resolution,
        "normalized_resolution_reference": normalized_resolution,
        "status": "matched",
        "matched_chunk_ids": [chunk.get("chunk_id") for chunk in chunks],
    }
def bm25_search_chunks(
    index: dict[str, Any],
    query: str,
    top_k: int = 30,
) -> list[dict[str, Any]]:
    bm25: BM25Okapi = index["bm25"]
    chunks: list[dict[str, Any]] = index["chunks"]

    scores = bm25.get_scores(tokenize(query))
    ranked_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:top_k]

    results = []

    for rank, idx in enumerate(ranked_indices, start=1):
        chunk = chunks[idx]
        metadata = chunk.get("metadata") or {}

        results.append(
            {
                "rank": rank,
                "bm25_score": float(scores[idx]),
                "chunk_id": chunk.get("chunk_id"),
                "source_type": chunk.get("source_type"),
                "doc_id": chunk.get("doc_id"),
                "title": chunk.get("title"),
                "article_id": metadata.get("article_id"),
                "resolution_reference": metadata.get("resolution_reference"),
                "text": chunk.get("text"),
            }
        )

    return results
def normalized_chunk_text(chunk: dict[str, Any]) -> str:
    """Forma comparable para impedir que el mismo texto sea positivo y negativo."""
    return normalize_text(str(chunk.get("text") or ""))


def normalized_chunk_resolution(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") or {}
    return normalize_resolution_reference(
        chunk.get("resolution_reference") or metadata.get("resolution_reference")
    )


def case_retrieval_query(case_payload: dict[str, Any]) -> str:
    """Texto del caso usado únicamente para recuperar un pool de distractores."""
    payload = {
        "title": (case_payload.get("source_trace") or {}).get("title"),
        "executive_summary": case_payload.get("executive_summary"),
        "legal_analysis": case_payload.get("legal_analysis"),
    }
    return json.dumps(payload, ensure_ascii=False)


def build_negative_candidate_pool(
    bm25_index: dict[str, Any],
    case_payload: dict[str, Any],
    candidate_result: ResolutionResult,
    max_candidates: int = DEFAULT_NEGATIVE_POOL_SIZE,
) -> list[dict[str, Any]]:
    """Construye distractores cercanos sin duplicar documentos relacionados.

    El pool se recupera antes de generar las preguntas. El LLM debe escoger de
    este conjunto cerrado cuáles son negativos seguros para cada pregunta.
    """
    positive_chunks = [candidate["chunk"] for candidate in candidate_result.candidates]
    excluded_ids = candidate_result.candidate_ids
    excluded_doc_ids = {
        str(chunk.get("doc_id")) for chunk in positive_chunks if chunk.get("doc_id")
    }
    excluded_texts = {
        normalized_chunk_text(chunk) for chunk in positive_chunks if normalized_chunk_text(chunk)
    }
    excluded_resolutions = {
        normalized_chunk_resolution(chunk)
        for chunk in positive_chunks
        if normalized_chunk_resolution(chunk)
    }

    retrieved = bm25_search_chunks(
        index=bm25_index,
        query=case_retrieval_query(case_payload),
        top_k=max(max_candidates * 5, max_candidates),
    )
    pool: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_doc_ids: set[str] = set()
    seen_texts: set[str] = set()
    seen_resolutions: set[str] = set()

    for candidate in retrieved:
        chunk_id = str(candidate.get("chunk_id") or "")
        doc_id = str(candidate.get("doc_id") or "")
        text_key = normalized_chunk_text(candidate)
        resolution_key = normalized_chunk_resolution(candidate)

        if not chunk_id or chunk_id in excluded_ids or chunk_id in seen_ids:
            continue
        if doc_id and (doc_id in excluded_doc_ids or doc_id in seen_doc_ids):
            continue
        if text_key and (text_key in excluded_texts or text_key in seen_texts):
            continue
        if resolution_key and (
            resolution_key in excluded_resolutions or resolution_key in seen_resolutions
        ):
            continue

        candidate = dict(candidate)
        candidate["candidate_id"] = chunk_id
        pool.append(candidate)
        seen_ids.add(chunk_id)
        if doc_id:
            seen_doc_ids.add(doc_id)
        if text_key:
            seen_texts.add(text_key)
        if resolution_key:
            seen_resolutions.add(resolution_key)

        if len(pool) >= max_candidates:
            break

    return pool


def negative_candidates_for_prompt(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "source_type": candidate.get("source_type"),
            "title": candidate.get("title"),
            "article_id": candidate.get("article_id"),
            "resolution_reference": candidate.get("resolution_reference"),
            "text": candidate.get("text"),
        }
        for candidate in pool
    ]


def validate_hard_negative_candidate_ids(
    selected_ids: list[str],
    negative_pool: list[dict[str, Any]],
    positive_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Valida IDs y bloquea colisiones documentales con los positivos."""
    selected = list(dict.fromkeys(str(value) for value in selected_ids if value))
    if not selected:
        raise ValueError("La pregunta no seleccionó ningún hard_negative_candidate_id.")

    pool_by_id = {candidate["candidate_id"]: candidate for candidate in negative_pool}
    unknown = sorted(set(selected) - set(pool_by_id))
    if unknown:
        raise ValueError(f"El LLM seleccionó hard_negative_candidate_ids inexistentes: {unknown}")

    positive_ids = {str(chunk.get("chunk_id")) for chunk in positive_chunks}
    positive_doc_ids = {str(chunk.get("doc_id")) for chunk in positive_chunks if chunk.get("doc_id")}
    positive_texts = {
        normalized_chunk_text(chunk) for chunk in positive_chunks if normalized_chunk_text(chunk)
    }
    positive_resolutions = {
        normalized_chunk_resolution(chunk)
        for chunk in positive_chunks
        if normalized_chunk_resolution(chunk)
    }

    collisions: list[str] = []
    validated: list[dict[str, Any]] = []
    for candidate_id in selected:
        candidate = pool_by_id[candidate_id]
        doc_id = str(candidate.get("doc_id") or "")
        text_key = normalized_chunk_text(candidate)
        resolution_key = normalized_chunk_resolution(candidate)
        if (
            candidate_id in positive_ids
            or (doc_id and doc_id in positive_doc_ids)
            or (text_key and text_key in positive_texts)
            or (resolution_key and resolution_key in positive_resolutions)
        ):
            collisions.append(candidate_id)
            continue
        validated.append(candidate)

    if collisions:
        raise ValueError(
            "El LLM eligió negativos que duplican un positivo por ID, documento, texto o "
            f"resolución: {sorted(collisions)}"
        )
    if not validated:
        raise ValueError("No quedó ningún hard negative válido después de comprobar colisiones.")
    return validated


def deduplicate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue

        seen.add(chunk_id)
        unique.append(chunk)

    return unique


def build_positive_context_text(chunks: list[dict[str, Any]]) -> str:
    blocks = []

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        block = {
            "chunk_id": chunk.get("chunk_id"),
            "source_type": chunk.get("source_type"),
            "title": chunk.get("title"),
            "article_id": metadata.get("article_id"),
            "resolution_reference": metadata.get("resolution_reference"),
            "text": chunk.get("text"),
        }
        blocks.append(json.dumps(block, ensure_ascii=False))

    return "\n\n".join(blocks)


# ============================================================
# 6. EXTRACCIÓN DEL RESUMEN DEL CASO
# ============================================================

def extract_case_payload_for_llm(case_data: dict[str, Any]) -> dict[str, Any]:
    source_trace = case_data.get("source_trace") or {}
    report = case_data.get("report") or {}
    legal_analysis = report.get("legal_analysis") or {}
    factual_density = case_data.get("factual_density_signals") or {}

    payload = {
        "source_trace": {
            "title": source_trace.get("title"),
            "resolution_reference_raw": source_trace.get("resolution_reference_raw"),
            "jurisprudence_type": source_trace.get("jurisprudence_type"),
            "pdf_filename": source_trace.get("pdf_filename"),
        },
        "executive_summary": report.get("executive_summary"),
        "legal_analysis": {
            "case_background": legal_analysis.get("case_background", []),
            "reported_acts": legal_analysis.get("reported_acts", []),
            "evidence_summary": legal_analysis.get("evidence_summary", []),
            "legal_reasoning": legal_analysis.get("legal_reasoning", []),
            "protective_measures_and_orders": legal_analysis.get("protective_measures_and_orders", []),
            "prosecutorial_or_procedural_outcomes": legal_analysis.get("prosecutorial_or_procedural_outcomes", []),
            "norms_cited": legal_analysis.get("norms_cited", []),
        },
        "factual_density_signals": factual_density,
    }

    return payload


def get_case_id(case_path: Path, case_data: dict[str, Any]) -> str:
    source_trace = case_data.get("source_trace") or {}
    pdf_filename = source_trace.get("pdf_filename")

    if pdf_filename:
        return Path(pdf_filename).stem

    return case_path.stem


def extract_case_reference_year(case_data: dict[str, Any]) -> int | None:
    """Extrae un año orientativo de la referencia, sin asumir fecha de vigencia."""
    source_trace = case_data.get("source_trace") or {}
    reference = str(source_trace.get("resolution_reference_raw") or "")
    years = re.findall(r"\b(?:19|20)\d{2}\b", reference)
    return int(years[-1]) if years else None


def build_temporal_context(
    case_data: dict[str, Any],
    positive_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Etiqueta combinaciones de fallos históricos y textos legales actuales."""
    legal_source_types = {
        "tipo_01_ley_30364",
        "tipo_02_codigo_penal",
        "tipo_03_codigo_procesal_penal",
    }
    selected_legal_sources = sorted(
        {
            str(chunk.get("source_type"))
            for chunk in positive_chunks
            if chunk.get("source_type") in legal_source_types
        }
    )
    reference_year = extract_case_reference_year(case_data)
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    requires_review = bool(
        selected_legal_sources
        and reference_year is not None
        and reference_year < current_year
    )
    return {
        "case_reference_year": reference_year,
        "legal_text_basis": "current_repository_snapshot",
        "selected_current_legal_sources": selected_legal_sources,
        "status": (
            "requires_historical_version_review"
            if requires_review
            else "no_known_temporal_conflict"
        ),
        "note": (
            "La referencia de la sentencia es anterior al snapshot legal actual; "
            "no asumir que penas o redacciones coinciden sin revisión histórica."
            if requires_review
            else "No se detectó automáticamente una combinación temporal que requiera revisión."
        ),
    }


# ============================================================
# 7. PROMPT Y LLAMADA AL LLM
# ============================================================

def build_system_prompt() -> str:
    schema = pydantic_schema_text(CaseQuestionBatch)

    return f"""
Eres un especialista en construcción de datasets para retrieval jurídico en Perú.

Recibirás un caso resumido, un conjunto CERRADO de documentos positivos candidatos y otro
conjunto CERRADO de posibles distractores. Debes generar preguntas coloquiales plausibles,
elegir los documentos que realmente permiten responderlas y seleccionar hard negatives que
sean cercanos pero que NO aporten la respuesta. También debes sintetizar el criterio abstracto
de la resolución en jurisprudencia_chunk_text.

REGLAS DE GROUNDING Y SELECCIÓN

1. positive_candidate_ids SOLO puede contener candidate_id copiados exactamente de
   candidate_documents. Nunca inventes IDs, artículos o fuentes fuera de esa lista.

2. Lee el texto literal de cada candidato. relation_types explica por qué entró al conjunto,
   pero NO prueba que sea positivo:
   - case_jurisprudence: resumen de la sentencia del caso;
   - source_article_anchor: artículo CP/CPP desde cuya página se halló la sentencia;
   - cited_in_jurisprudence: norma citada en el resumen de la resolución;
   - page_concordance: concordancia de la página del artículo ancla en LP Derecho.
   Una concordancia es solo candidata; no la selecciones si su texto no responde la pregunta.

3. Selecciona TODOS y SOLO los candidatos necesarios para responder eficazmente cada pregunta.
   Puede haber uno o varios positivos. No conviertas automáticamente la jurisprudencia, el
   artículo ancla ni todas las concordancias en positivos.

4. Cada pregunta debe ser contestable por los candidatos seleccionados. Si los candidatos no
   contienen sustento para una categoría, no generes una pregunta de esa categoría.

REGLAS PARA HARD NEGATIVES

5. hard_negative_candidate_ids SOLO puede contener candidate_id copiados exactamente de
   negative_candidate_documents. Nunca uses IDs de candidate_documents ni inventes IDs.

6. Un hard negative debe parecer relacionado por vocabulario o tema, pero NO debe responder,
   completar ni aportar una regla necesaria para contestar la pregunta. Si un artículo regula
   directamente el derecho, trámite, pena, prueba o facultad consultada, NO es negativo.

7. Una sentencia con un criterio contrario tampoco es negativa si ayudaría a explicar la
   respuesta o revela una controversia jurídica relevante. Ante cualquier duda, no la elijas.

8. Justifica brevemente por qué cada grupo de negativos es cercano pero insuficiente.

REGLAS PARA LAS PREGUNTAS

9. Las preguntas deben sonar como las formularía una víctima: naturales, ciudadanas y no
   técnicas. Pueden reflejar temor, vergüenza, desconocimiento, dependencia económica,
   preocupación por hijos o desconfianza en el sistema.

10. No inventes hechos fuera del caso resumido y no reveles nombres ni otros datos personales.

11. No respondas la pregunta. expected_answer_focus solo describe qué debería responder el RAG.

12. Diversifica temas únicamente cuando exista respaldo: identificación del delito, medidas de
   protección, prueba, procedimiento, reparación, sanción, hijos, violencia psicológica u otros.

13. Cuando la sentencia contenga un principio directamente útil para una víctima, genera al
   menos una pregunta doctrina_jurisprudencial y selecciona el candidato case_jurisprudence.
   Si la doctrina no tiene aplicación directa o su texto no responde la pregunta, no la fuerces.

REGLA TEMPORAL

14. Los artículos legales provienen del snapshot actual del repositorio, mientras que la
   sentencia puede aplicar una redacción histórica. No afirmes que una pena, plazo o redacción
   histórica sigue vigente. Si el caso es antiguo y la pregunta depende de una cifra o versión
   normativa, formula la pregunta sin fijar esa cifra y deja claro en expected_answer_focus que
   debe comprobarse la norma aplicable en el tiempo.

REGLAS PARA jurisprudencia_chunk_text

El campo jurisprudencia_chunk_text debe contener una síntesis de 3-5 oraciones con:
- El criterio o principio jurídico general que establece esta resolución.
- La decisión adoptada y su fundamento legal.
- Su relevancia o aplicación en contextos de violencia familiar.

PROHIBIDO en este campo:
- Nombres propios de personas (ni anonimizados).
- Fechas específicas del caso.
- Hechos particulares del expediente.

El texto debe ser abstracto, aplicable a casos futuros similares y jurídicamente conciso.

Responde estrictamente con este JSON Schema.
Respeta exactamente los valores permitidos y los candidate_id disponibles.

{schema}
""".strip()


def build_user_prompt(
    case_payload: dict[str, Any],
    n_questions: int,
    correction_feedback: str | None = None,
) -> str:
    correction_block = ""
    if correction_feedback:
        correction_block = f"""

CORRECCIÓN OBLIGATORIA DE UN INTENTO ANTERIOR:
{correction_feedback}
Vuelve a generar el lote completo y copia todos los IDs exactamente de las listas disponibles.
"""
    return f"""
Genera entre 4 y {n_questions} preguntas coloquiales basadas en este caso y en los
documentos candidatos. Prima la fidelidad jurídica sobre alcanzar el máximo de preguntas.
{correction_block}

Entrada completa en JSON:

{json.dumps(case_payload, ensure_ascii=False, indent=2)}
""".strip()


def call_llm_for_case(
    client: OpenAI,
    case_payload: dict[str, Any],
    n_questions: int,
    model: str,
    correction_feedback: str | None = None,
) -> CaseQuestionBatch:
    response = client.chat.completions.create(
        model=model,
        temperature=MODEL_TEMPERATURE,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {
                "role": "user",
                "content": build_user_prompt(case_payload, n_questions, correction_feedback),
            },
        ],
        stream=False,
        response_format={"type":"json_object"},
        extra_body={"reasoning": {"enabled": True}}
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("El modelo no devolvió contenido.")

    try:
        raw_json = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"El modelo no devolvió JSON válido. Content: {content[:500]}") from exc

    parsed = CaseQuestionBatch.model_validate(raw_json)

    return parsed


# ============================================================
# 8. CONSTRUCCIÓN DEL DATASET FINAL
# ============================================================

def build_dataset_records_for_case(
    case_path: Path,
    case_data: dict[str, Any],
    llm_output: CaseQuestionBatch,
    lookup: dict[str, Any],
    candidate_result: ResolutionResult,
    negative_candidate_pool: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Retorna (records, chunk_update) donde chunk_update contiene la síntesis
    jurídica generada por el LLM para actualizar el text del chunk de jurisprudencia.
    """
    case_id = get_case_id(case_path, case_data)

    jurisprudence_chunks, jurisprudence_match_info = resolve_case_jurisprudence(
        case_data=case_data,
        lookup=lookup,
    )

    records = []
    candidates_by_id = {
        candidate["candidate_id"]: candidate
        for candidate in candidate_result.candidates
    }

    validated_questions: list[
        tuple[GeneratedQuestion, list[str], list[dict[str, Any]], list[dict[str, Any]]]
    ] = []
    for question in llm_output.questions:
        selected_ids = validate_positive_candidate_ids(
            question.positive_candidate_ids,
            candidate_result,
        )
        positive_chunks = [candidates_by_id[candidate_id]["chunk"] for candidate_id in selected_ids]
        hard_negative_candidates = validate_hard_negative_candidate_ids(
            question.hard_negative_candidate_ids,
            negative_candidate_pool,
            positive_chunks,
        )
        validated_questions.append(
            (question, selected_ids, positive_chunks, hard_negative_candidates)
        )

    # Solo se modifica el chunk en memoria después de validar el lote completo.
    # Así un reintento fallido no contamina los siguientes intentos.
    chunk_update: dict[str, Any] = {}
    synthesis_text = (llm_output.jurisprudencia_chunk_text or "").strip()
    matched_jp_ids = jurisprudence_match_info.get("matched_chunk_ids", [])
    if synthesis_text and matched_jp_ids:
        matched_jp_set = set(matched_jp_ids)
        for chunk in jurisprudence_chunks:
            if chunk.get("chunk_id") in matched_jp_set:
                chunk["text"] = synthesis_text
        for chunk_id in matched_jp_ids:
            chunk_update[chunk_id] = {
                "chunk_id": chunk_id,
                "new_text": synthesis_text,
                "case_id": case_id,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

    for i, (
        question,
        selected_ids,
        positive_chunks,
        hard_negative_candidates,
    ) in enumerate(validated_questions, start=1):

        positive_chunk_ids = {
            chunk["chunk_id"]
            for chunk in positive_chunks
            if chunk.get("chunk_id")
        }

        # Campos EDA pre-calculados
        pos_source_types = list(dict.fromkeys(
            c.get("source_type", "") for c in positive_chunks if c.get("source_type")
        ))
        pos_articles = [
            (c.get("metadata") or {}).get("article_id")
            for c in positive_chunks
            if (c.get("metadata") or {}).get("article_id")
        ]

        record = {
            "dataset_id": f"{case_id}_q{i:03d}",
            "case_id": case_id,
            "source_file": str(case_path.relative_to(PROJECT_ROOT)),

            "query": question.query,
            "normalized_query": question.normalized_query,
            "topic": question.topic,
            "barrier": question.barrier,
            "victim_voice_rationale": question.victim_voice_rationale,
            "expected_answer_focus": question.expected_answer_focus,
            "confidence": question.confidence,

            "positive_candidate_ids": selected_ids,
            "positive_selection_reason": question.positive_selection_reason,
            "selected_candidate_relations": {
                candidate_id: candidates_by_id[candidate_id]["relations"]
                for candidate_id in selected_ids
            },

            "positive_chunk_ids": sorted(positive_chunk_ids),

            "positive_chunks": [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "source_type": chunk.get("source_type"),
                    "doc_id": chunk.get("doc_id"),
                    "title": chunk.get("title"),
                    "article_id": (chunk.get("metadata") or {}).get("article_id"),
                    "resolution_reference": (chunk.get("metadata") or {}).get("resolution_reference"),
                    "text": chunk.get("text"),
                }
                for chunk in positive_chunks
            ],

            "positive_context_text": build_positive_context_text(positive_chunks),
            "positive_context_count": len(positive_chunks),

            "hard_negative_candidate_ids": [
                candidate["candidate_id"] for candidate in hard_negative_candidates
            ],
            "hard_negative_selection_reason": question.hard_negative_selection_reason,

            "hard_negative_chunk_ids": [
                candidate["chunk_id"]
                for candidate in hard_negative_candidates
            ],

            "hard_negative_chunks": hard_negative_candidates,

            "candidate_set_id": case_id,
            "candidate_count": len(candidate_result.candidates),
            "negative_candidate_pool_count": len(negative_candidate_pool),
            "unresolved_candidate_refs": candidate_result.unresolved_references,
            "jurisprudence_match_info": jurisprudence_match_info,
            "temporal_context": build_temporal_context(case_data, positive_chunks),

            "source_trace": case_data.get("source_trace", {}),
            "generation_metadata": {
                "prompt_version": PROMPT_VERSION,
                "resolver_version": RESOLVER_VERSION,
                "negative_selection": "llm_from_closed_bm25_pool",
            },

            # ── Campos EDA (pre-calculados para análisis directo con pandas/Counter) ──
            "query_length": len(question.query),
            "negative_count": len(hard_negative_candidates),
            "unresolved_count": len(candidate_result.unresolved_references),
            "positive_source_types": pos_source_types,
            "positive_articles": pos_articles,
            "has_jurisprudence_positive": any(
                c.get("source_type") == "tipo_04_jurisprudencia" for c in positive_chunks
            ),
            "has_institutional_positive": any(
                c.get("source_type") == "tipo_05_documentos_institucionales" for c in positive_chunks
            ),
            "jurisprudence_matched": jurisprudence_match_info.get("status") == "matched",
            "neg_bm25_scores": [c.get("bm25_score", 0.0) for c in hard_negative_candidates],
            "negative_source_types": [c.get("source_type", "") for c in hard_negative_candidates],
        }

        records.append(record)

    return records, chunk_update
FINETUNING_PROMPT = "Represent this sentence for searching relevant passages: "


def build_training_records(
    records: list[dict[str, Any]],
    max_negatives: int = 10,
) -> list[dict[str, Any]]:
    """
    Genera el dataset de entrenamiento en el formato esperado por los frameworks
    de fine-tuning de embeddings (sentence-transformers, GTE, etc.).

    Una fila por query con pos y neg como listas de texto.
    """
    training = []

    for idx, record in enumerate(records):
        positives = record.get("positive_chunks", [])
        negatives = record.get("hard_negative_chunks", [])

        if not positives or not negatives:
            continue

        positive_texts = list(
            dict.fromkeys(chunk["text"] for chunk in positives if chunk.get("text"))
        )
        negative_texts = list(
            dict.fromkeys(
                chunk["text"] for chunk in negatives[:max_negatives] if chunk.get("text")
            )
        )
        normalized_positives = {normalize_text(text) for text in positive_texts}
        normalized_negatives = {normalize_text(text) for text in negative_texts}
        if normalized_positives & normalized_negatives:
            raise ValueError(
                f"El registro {record.get('dataset_id')} contiene el mismo texto como "
                "positivo y negativo."
            )

        temporal_context = record.get("temporal_context") or {}
        training.append(
            {
                "id": str(idx),
                "query": record["query"],
                "pos": positive_texts,
                "neg": negative_texts,
                "prompt": FINETUNING_PROMPT,
                # Metadatos útiles para agrupar y analizar el dataset.
                "dataset_id": record["dataset_id"],
                "case_id": record["case_id"],
                "topic": record["topic"],
                "barrier": record["barrier"],
                "temporal_status": temporal_context.get("status"),
                "case_reference_year": temporal_context.get("case_reference_year"),
            }
        )

    return training


def process_cases(
    chunks_path: Path,
    cases_dir: Path,
    output_dir: Path,
    cp_articles_path: Path,
    cpp_articles_path: Path,
    ley_30364_path: Path,
    context_units_path: Path,
    structured_entries_path: Path,
    model: str,
    n_questions: int,
    limit: int | None,
    updates_path: Path,
    max_attempts: int,
    negative_pool_size: int,
) -> None:

    if not 4 <= n_questions <= 12:
        raise ValueError("n_questions debe estar entre 4 y 12.")
    if max_attempts < 1:
        raise ValueError("max_attempts debe ser al menos 1.")
    if negative_pool_size < 1:
        raise ValueError("negative_pool_size debe ser al menos 1.")

    load_dotenv()
    client = OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY"),base_url="https://openrouter.ai/api/v1")

    resolver = LegalCandidateResolver.from_paths(
        cp_articles_path=cp_articles_path,
        cpp_articles_path=cpp_articles_path,
        ley_30364_path=ley_30364_path,
        context_units_path=context_units_path,
        structured_entries_path=structured_entries_path,
    )
    snapshot_chunks = load_chunks(chunks_path)
    chunks = merge_corpus_chunks(snapshot_chunks, resolver.all_article_chunks())
    print(f"[INFO] Chunks cargados y completados: {len(chunks)}")

    bm25_index = build_bm25(chunks)
    print("[INFO] Índice BM25 construido.")

    lookup = build_lookup_indexes(chunks)
    print("[INFO] Índices determinísticos listos.")

    case_paths = sorted(cases_dir.glob("*.json"))
    if limit is not None:
        case_paths = case_paths[:limit]

    print(f"[INFO] Casos a procesar: {len(case_paths)}")

    output_jsonl = output_dir / "questions_with_positive_context.jsonl"
    errors_jsonl = output_dir / "generation_errors.jsonl"
    candidate_sets_jsonl = output_dir / "candidate_sets.jsonl"
    manifest_json = output_dir / "run_manifest.json"
    triples_jsonl = output_dir / "training_triples.jsonl"
    updates_jsonl = updates_path

    for generated_path in (
        output_jsonl,
        errors_jsonl,
        candidate_sets_jsonl,
        manifest_json,
        triples_jsonl,
        updates_jsonl,
    ):
        if generated_path.exists():
            generated_path.unlink()

    total_records = 0
    resolved_candidate_sets = 0
    processed_cases = 0
    failed_cases = 0
    skipped_not_candidate = 0
    llm_call_attempts = 0
    retried_cases = 0
    resolution_totals: dict[str, int] = defaultdict(int)
    all_chunk_updates: dict[str, Any] = {}  # chunk_id → update entry
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for case_path in case_paths:
        print(f"\n[INFO] Procesando: {case_path.name}")

        try:
            case_data = read_json(case_path)

            factual_density = case_data.get("factual_density_signals") or {}
            if not factual_density.get("is_dataset_candidate", True):
                skipped_not_candidate += 1
                print(f"[WARN] Saltando caso no candidato: {case_path.name}")
                continue

            case_payload = extract_case_payload_for_llm(case_data)
            case_id = get_case_id(case_path, case_data)

            jurisprudence_chunks, _ = resolve_case_jurisprudence(
                case_data=case_data,
                lookup=lookup,
            )
            candidate_result = resolver.resolve_case(
                case_id=case_id,
                jurisprudence_chunks=jurisprudence_chunks,
            )
            if not candidate_result.candidates:
                raise ValueError(f"El caso {case_id} no tiene documentos candidatos resolubles.")

            for relation_type, count in candidate_result.relation_counts.items():
                resolution_totals[relation_type] += count
            resolution_totals["unresolved_references"] += len(candidate_result.unresolved_references)

            negative_candidate_pool = build_negative_candidate_pool(
                bm25_index=bm25_index,
                case_payload=case_payload,
                candidate_result=candidate_result,
                max_candidates=negative_pool_size,
            )
            if not negative_candidate_pool:
                raise ValueError(f"El caso {case_id} no tiene distractores resolubles.")

            case_payload["temporal_notice"] = {
                "legal_text_basis": "current_repository_snapshot",
                "case_reference_year": extract_case_reference_year(case_data),
                "instruction": (
                    "La sentencia puede aplicar una versión histórica. Evitar afirmar que penas, "
                    "plazos o redacciones antiguas siguen vigentes sin verificación temporal."
                ),
            }
            case_payload["candidate_documents"] = candidates_for_prompt(candidate_result)
            case_payload["negative_candidate_documents"] = negative_candidates_for_prompt(
                negative_candidate_pool
            )
            candidate_set_record = candidate_result.as_dict(case_id)
            candidate_set_record["source_file"] = str(case_path.relative_to(PROJECT_ROOT))
            candidate_set_record["resolver_version"] = RESOLVER_VERSION
            candidate_set_record["negative_candidate_pool"] = negative_candidate_pool
            candidate_set_record["negative_candidate_count"] = len(negative_candidate_pool)
            append_jsonl(candidate_set_record, candidate_sets_jsonl)
            resolved_candidate_sets += 1

            correction_feedback: str | None = None
            records: list[dict[str, Any]] | None = None
            chunk_update: dict[str, Any] | None = None
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                llm_call_attempts += 1
                try:
                    llm_output = call_llm_for_case(
                        client=client,
                        case_payload=case_payload,
                        n_questions=n_questions,
                        model=model,
                        correction_feedback=correction_feedback,
                    )

                    # Reforzamos case_id correcto aunque el modelo devuelva otro.
                    llm_output.case_id = case_id
                    records, chunk_update = build_dataset_records_for_case(
                        case_path=case_path,
                        case_data=case_data,
                        llm_output=llm_output,
                        lookup=lookup,
                        candidate_result=candidate_result,
                        negative_candidate_pool=negative_candidate_pool,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt >= max_attempts:
                        raise
                    if attempt == 1:
                        retried_cases += 1
                    correction_feedback = (
                        f"El intento {attempt} fue rechazado por esta validación: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    wait_seconds = min(2 ** (attempt - 1), 4)
                    print(
                        f"[WARN] Reintentando {case_id} ({attempt + 1}/{max_attempts}) "
                        f"después de: {exc}"
                    )
                    time.sleep(wait_seconds)

            if records is None or chunk_update is None:
                raise RuntimeError(
                    f"No se generó un lote válido para {case_id}: {last_error}"
                )

            for record in records:
                append_jsonl(record, output_jsonl)

            all_chunk_updates.update(chunk_update)
            if chunk_update:
                print(f"[OK] Síntesis de chunk generada para: {list(chunk_update.keys())}")

            total_records += len(records)
            processed_cases += 1
            print(f"[OK] Preguntas generadas: {len(records)}")

        except Exception as exc:
            failed_cases += 1
            error_record = {
                "source_file": str(case_path),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
            append_jsonl(error_record, errors_jsonl)
            print(f"[ERROR] Falló {case_path.name}: {exc}")

    manifest = {
        "schema_version": 3,
        "prompt_version": PROMPT_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generation_config": {
            "model": model,
            "temperature": MODEL_TEMPERATURE,
            "n_questions_max": n_questions,
            "limit": limit,
            "max_attempts_per_case": max_attempts,
            "negative_pool_size": negative_pool_size,
            "negative_selection": "llm_from_closed_bm25_pool",
        },
        "source_files": {
            **resolver.source_files_summary(),
            "document_chunks_snapshot": portable_path(chunks_path),
        },
        "corpus": {
            "snapshot_chunk_count": len(snapshot_chunks),
            "effective_chunk_count": len(chunks),
        },
        "results": {
            "case_count_requested": len(case_paths),
            "candidate_set_count": resolved_candidate_sets,
            "case_count_processed": processed_cases,
            "case_count_failed": failed_cases,
            "case_count_skipped_not_dataset_candidate": skipped_not_candidate,
            "question_count": total_records,
            "llm_call_attempts": llm_call_attempts,
            "retried_cases": retried_cases,
            "candidate_resolution_totals": dict(sorted(resolution_totals.items())),
        },
    }
    # Escribir archivo de actualizaciones de chunks de jurisprudencia
    if all_chunk_updates:
        write_jsonl(list(all_chunk_updates.values()), updates_jsonl)
        print(f"\n[INFO] Síntesis de chunks escritas: {len(all_chunk_updates)} → {updates_jsonl}")
    else:
        print("\n[WARN] No se generaron síntesis de chunks (posiblemente ningún caso matcheó jurisprudencia).")

    # Generar archivo final de triples de entrenamiento (query / positive_text / negative_text)
    if output_jsonl.exists():
        with output_jsonl.open(encoding="utf-8") as f:
            all_records = [json.loads(line) for line in f if line.strip()]
        triples = build_training_records(all_records, max_negatives=10)
        write_jsonl(triples, triples_jsonl)
        print(f"[INFO] Triples de entrenamiento: {len(triples)} → {triples_jsonl}")
    else:
        print("[WARN] No se generaron triples: el dataset principal está vacío.")

    artifact_paths = {
        "candidate_sets": candidate_sets_jsonl,
        "questions": output_jsonl,
        "errors": errors_jsonl,
        "training_triples": triples_jsonl,
        "jurisprudence_chunk_updates": updates_jsonl,
    }
    manifest["artifacts"] = {
        name: portable_path(path)
        for name, path in artifact_paths.items()
        if path.exists()
    }
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n============================================================")
    print("[RESUMEN]")
    print(f"Total de preguntas generadas: {total_records}")
    print(f"Dataset: {output_jsonl}")
    print(f"Triples entrenamiento: {triples_jsonl}")
    print(f"Errores: {errors_jsonl}")
    print(f"Conjuntos candidatos: {candidate_sets_jsonl}")
    print(f"Resumen de ejecución: {manifest_json}")
    print(f"Chunk updates: {updates_jsonl} ({len(all_chunk_updates)} entradas)")
    print("============================================================")


# ============================================================
# 9. CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera dataset de preguntas jurídicas coloquiales con positive context para contrastive learning."
    )

    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=DEFAULT_CHUNKS_PATH,
        help="Ruta a document_chunks_all.jsonl.",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=DEFAULT_CASES_DIR,
        help="Carpeta con JSONs resumidos por ResumeAI.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta de salida del dataset.",
    )
    parser.add_argument(
        "--updates-path",
        type=Path,
        default=DEFAULT_UPDATES_PATH,
        help="Ruta para las síntesis generadas de chunks de jurisprudencia.",
    )
    parser.add_argument("--cp-articles-path", type=Path, default=DEFAULT_CP_ARTICLES_PATH)
    parser.add_argument("--cpp-articles-path", type=Path, default=DEFAULT_CPP_ARTICLES_PATH)
    parser.add_argument("--ley-30364-path", type=Path, default=DEFAULT_LEY_30364_PATH)
    parser.add_argument("--context-units-path", type=Path, default=DEFAULT_CONTEXT_UNITS_PATH)
    parser.add_argument("--structured-entries-path", type=Path, default=DEFAULT_STRUCTURED_ENTRIES_PATH)
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help="Modelo OpenAI a usar.",
    )
    parser.add_argument(
        "--n-questions",
        type=int,
        default=5,
        help="Máximo de preguntas por caso (default: 5, hasta 890 para 178 casos).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Procesa solo los primeros N casos. Útil para pruebas.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help="Máximo de llamadas por caso cuando la respuesta no supera la validación.",
    )
    parser.add_argument(
        "--negative-pool-size",
        type=int,
        default=DEFAULT_NEGATIVE_POOL_SIZE,
        help="Cantidad de distractores BM25 mostrados al LLM para escoger negativos seguros.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    process_cases(
        chunks_path=args.chunks_path,
        cases_dir=args.cases_dir,
        output_dir=args.output_dir,
        cp_articles_path=args.cp_articles_path,
        cpp_articles_path=args.cpp_articles_path,
        ley_30364_path=args.ley_30364_path,
        context_units_path=args.context_units_path,
        structured_entries_path=args.structured_entries_path,
        model=args.model,
        n_questions=args.n_questions,
        limit=args.limit,
        updates_path=args.updates_path,
        max_attempts=args.max_attempts,
        negative_pool_size=args.negative_pool_size,
    )
