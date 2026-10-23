"""Resolución determinística de candidatos jurídicos para generar el dataset.

Este módulo no llama a ningún LLM. Une cuatro fuentes de evidencia:

1. la jurisprudencia que dio origen al caso;
2. el artículo ancla del CP/CPP desde el que LP Derecho enlazó el caso;
3. los artículos citados en el resumen estructurado de la resolución;
4. las concordancias publicadas en la página índice de LP Derecho.

El resultado es un conjunto cerrado de documentos con texto literal. El LLM
solo puede seleccionar IDs de este conjunto; nunca propone artículos libres.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SOURCE_CP = "tipo_02_codigo_penal"
SOURCE_CPP = "tipo_03_codigo_procesal_penal"
SOURCE_LEY_30364 = "tipo_01_ley_30364"
SOURCE_JURISPRUDENCE = "tipo_04_jurisprudencia"
RESOLVER_VERSION = "deterministic-legal-candidates-v1"

CONCORDANCE_CODE_TO_SOURCE = {
    "CP": SOURCE_CP,
    "CPP": SOURCE_CPP,
    "NCPP": SOURCE_CPP,
}

NORM_NAME_TO_SOURCE = {
    "codigo penal": SOURCE_CP,
    "código penal": SOURCE_CP,
    "codigo procesal penal (ncpp/cpp de 2004)": SOURCE_CPP,
    "código procesal penal (ncpp/cpp de 2004)": SOURCE_CPP,
    "codigo procesal penal": SOURCE_CPP,
    "código procesal penal": SOURCE_CPP,
    "ley 30364 (violencia contra la mujer)": SOURCE_LEY_30364,
    "ley 30364": SOURCE_LEY_30364,
}

SOURCE_CONFIG = {
    SOURCE_CP: {
        "doc_prefix": "tipo02_cp_art",
        "doc_type": "codigo_penal_article",
        "issuing_body": "Código Penal",
    },
    SOURCE_CPP: {
        "doc_prefix": "tipo03_cpp_art",
        "doc_type": "codigo_procesal_penal_article",
        "issuing_body": "Código Procesal Penal",
    },
    SOURCE_LEY_30364: {
        "doc_prefix": "tipo01_ley30364_art",
        "doc_type": "ley_article",
        "issuing_body": "Ley 30364",
    },
}


def normalize_article_id(value: Any) -> str:
    """Normaliza un identificador sin confundir artículos con sus numerales."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = re.sub(r"^(ART[IÍ]CULO|ART\.)\s*", "", text)
    text = re.sub(r"\s+", "", text)
    return text.strip(".°º")


def article_reference_aliases(value: Any) -> list[str]:
    """Devuelve formas resolubles para artículos, numerales y rangos.

    Ejemplos:
      - ``429.1`` -> ``[429.1, 429]``
      - ``425.3.B`` -> ``[425.3.B, 425]``
      - ``162-164`` -> ``[162-164, 162, 163, 164]``

    El artículo padre se usa porque los chunks almacenan el artículo completo,
    incluidos sus numerales e incisos.
    """
    normalized = normalize_article_id(value)
    if not normalized:
        return []

    aliases = [normalized]
    range_match = re.fullmatch(r"(\d+)-(\d+)", normalized)
    if range_match:
        start, end = map(int, range_match.groups())
        if start <= end and end - start <= 20:
            aliases.extend(str(number) for number in range(start, end + 1))

    parent_match = re.match(r"(\d+(?:-[A-Z])?)", normalized)
    if parent_match:
        parent = parent_match.group(1)
        if parent not in aliases:
            aliases.append(parent)

    # Artículos del Título Preliminar: "IX TP", "II.1" o
    # "VIII Título Preliminar" se almacenan como números romanos.
    roman_parent = re.match(
        r"^([IVXLCDM]+)(?:\.\d+|T[IÍ]TULOPRELIMINAR|TP|$)",
        normalized,
    )
    if roman_parent and roman_parent.group(1) not in aliases:
        aliases.append(roman_parent.group(1))

    return list(dict.fromkeys(aliases))


def normalize_url(value: Any) -> str:
    text = str(value or "").strip()
    return text.rstrip("/") + "/" if text else ""


def portable_path(path: Path) -> str:
    """Evita incrustar el directorio personal del autor en los manifiestos."""
    resolved = path.resolve()
    for parent in resolved.parents:
        if (parent / "pyproject.toml").exists():
            return str(resolved.relative_to(parent))
    return str(path)


def _slug(value: Any) -> str:
    normalized = normalize_article_id(value).lower()
    slug = re.sub(r"[^a-z0-9-]+", "_", normalized).strip("_")
    return slug or "sin_id"


def _read_json_rows(path: Path, list_key: str | None = None) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if list_key and isinstance(data.get(list_key), list):
        return data[list_key]
    raise ValueError(f"Se esperaba una lista JSON en {path}")


def article_to_chunk(article: dict[str, Any], source_type: str) -> dict[str, Any]:
    """Convierte un artículo completo en el mismo formato que el corpus RAG."""
    config = SOURCE_CONFIG[source_type]
    article_id = str(article.get("article_id") or "sin_id")
    doc_id = f"{config['doc_prefix']}_{_slug(article_id)}"
    title = article.get("title") or article.get("heading") or f"Artículo {article_id}"
    return {
        "chunk_id": f"chunk_{doc_id}_01",
        "doc_id": doc_id,
        "doc_type": config["doc_type"],
        "source_type": source_type,
        "chunk_type": "article_full",
        "title": title,
        "text": article.get("text") or "",
        "order": 1,
        "metadata": {
            "source_url": article.get("source_url"),
            "article_id": article_id,
            "resolution_reference": None,
            "resolution_type": None,
            "issuing_body": config["issuing_body"],
            "topic_tags": [source_type, "articulo"],
            "parent_unit_type": "structured_article_text",
            "raw_article_id": article_id,
        },
        "retrieval_tags": [source_type, "articulo"],
    }


@dataclass
class ResolutionResult:
    candidates: list[dict[str, Any]]
    unresolved_references: list[dict[str, Any]]
    relation_counts: dict[str, int]

    @property
    def candidate_ids(self) -> set[str]:
        return {candidate["candidate_id"] for candidate in self.candidates}

    def as_dict(self, case_id: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "candidates": self.candidates,
            "candidate_count": len(self.candidates),
            "unresolved_references": self.unresolved_references,
            "relation_counts": self.relation_counts,
        }


class LegalCandidateResolver:
    """Índice de textos legales y relaciones jurisprudenciales."""

    def __init__(
        self,
        article_rows: dict[str, list[dict[str, Any]]],
        context_units: list[dict[str, Any]],
        structured_entries: list[dict[str, Any]],
        source_files: dict[str, Path] | None = None,
    ) -> None:
        self.article_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._article_chunks: dict[str, dict[str, Any]] = {}

        for source_type, articles in article_rows.items():
            for article in articles:
                chunk = article_to_chunk(article, source_type)
                chunk_id = chunk["chunk_id"]

                # Algunos scrapers antiguos produjeron IDs duplicados. Se
                # conserva la versión con más texto y se registra una sola vez.
                current = self._article_chunks.get(chunk_id)
                if current is None or len(chunk.get("text", "")) > len(current.get("text", "")):
                    self._article_chunks[chunk_id] = chunk

        # Se indexan las versiones finales para que un duplicado descartado no
        # reaparezca al resolver un artículo.
        for chunk in self._article_chunks.values():
            source_type = chunk["source_type"]
            article_id = normalize_article_id((chunk.get("metadata") or {}).get("article_id"))
            aliases = [article_id]
            # Corrige artefactos como "23Autor" sin alterar "121-B".
            malformed = re.match(r"^(\d+)[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ]+", article_id)
            if malformed:
                aliases.append(malformed.group(1))
            for alias in aliases:
                if alias:
                    self.article_index[(source_type, alias)].append(chunk)

        self.context_by_case_id = {
            str(row.get("entry_id")): row
            for row in context_units
            if row.get("entry_id")
        }
        self.structured_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in structured_entries:
            entry_url = normalize_url(row.get("lp_entry_url"))
            if entry_url:
                # Una jurisprudencia puede aparecer enlazada desde varios
                # artículos. Cada fila conserva las concordancias de su página
                # índice; agrupar evita perder esas rutas de procedencia.
                self.structured_by_url[entry_url].append(row)
        self.source_files = source_files or {}

    @classmethod
    def from_paths(
        cls,
        cp_articles_path: Path,
        cpp_articles_path: Path,
        ley_30364_path: Path,
        context_units_path: Path,
        structured_entries_path: Path,
    ) -> "LegalCandidateResolver":
        paths = {
            "codigo_penal": cp_articles_path,
            "codigo_procesal_penal": cpp_articles_path,
            "ley_30364": ley_30364_path,
            "jurisprudence_context_units": context_units_path,
            "jurisprudence_structured_entries": structured_entries_path,
        }
        missing = [str(path) for path in paths.values() if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Faltan fuentes para resolver candidatos: {missing}")

        article_rows = {
            SOURCE_CP: _read_json_rows(cp_articles_path),
            SOURCE_CPP: _read_json_rows(cpp_articles_path),
            SOURCE_LEY_30364: _read_json_rows(ley_30364_path, list_key="articles"),
        }
        return cls(
            article_rows=article_rows,
            context_units=_read_json_rows(context_units_path),
            structured_entries=_read_json_rows(structured_entries_path),
            source_files=paths,
        )

    def source_files_summary(self) -> dict[str, str]:
        return {
            name: portable_path(path)
            for name, path in sorted(self.source_files.items())
        }

    def all_article_chunks(self) -> list[dict[str, Any]]:
        return sorted(self._article_chunks.values(), key=lambda item: item["chunk_id"])

    def resolve_article(self, source_type: str, article_reference: Any) -> list[dict[str, Any]]:
        resolved: dict[str, dict[str, Any]] = {}
        for alias in article_reference_aliases(article_reference):
            for chunk in self.article_index.get((source_type, alias), []):
                resolved[chunk["chunk_id"]] = chunk
        return list(resolved.values())

    def resolve_case(
        self,
        case_id: str,
        jurisprudence_chunks: Iterable[dict[str, Any]],
    ) -> ResolutionResult:
        context = self.context_by_case_id.get(case_id)
        if context is None:
            raise KeyError(f"No se encontró {case_id} en jurisprudence_context_units.json")

        candidates: dict[str, dict[str, Any]] = {}
        unresolved: list[dict[str, Any]] = []
        relation_counts: dict[str, int] = defaultdict(int)

        def add_chunk(chunk: dict[str, Any], relation: dict[str, Any]) -> None:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id or not chunk.get("text"):
                return
            candidate = candidates.setdefault(
                chunk_id,
                {
                    "candidate_id": chunk_id,
                    "chunk": chunk,
                    "relations": [],
                },
            )
            relation_key = json.dumps(relation, ensure_ascii=False, sort_keys=True)
            existing = {
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in candidate["relations"]
            }
            if relation_key not in existing:
                candidate["relations"].append(relation)
                relation_counts[f"{relation['relation_type']}_candidate_edges"] += 1

        def add_article(
            source_type: str,
            raw_article_id: Any,
            relation_type: str,
            confidence: str,
            evidence: dict[str, Any],
        ) -> None:
            relation_counts[f"{relation_type}_references_total"] += 1
            matches = self.resolve_article(source_type, raw_article_id)
            if not matches:
                unresolved.append(
                    {
                        "relation_type": relation_type,
                        "source_type": source_type,
                        "raw_article_id": raw_article_id,
                        "normalized_article_id": normalize_article_id(raw_article_id),
                        "evidence": evidence,
                    }
                )
                return
            relation_counts[f"{relation_type}_references_resolved"] += 1
            relation = {
                "relation_type": relation_type,
                "confidence": confidence,
                "raw_article_id": raw_article_id,
                "evidence": evidence,
            }
            for chunk in matches:
                add_chunk(chunk, relation)

        exact_jurisprudence = [
            chunk
            for chunk in jurisprudence_chunks
            if chunk.get("doc_id") == f"tipo04_{case_id}"
            or f"_{case_id}_" in str(chunk.get("chunk_id", ""))
        ]
        selected_jurisprudence = exact_jurisprudence or list(jurisprudence_chunks)
        relation_counts["case_jurisprudence_references_total"] += 1
        if selected_jurisprudence:
            relation_counts["case_jurisprudence_references_resolved"] += 1
        else:
            unresolved.append(
                {
                    "relation_type": "case_jurisprudence",
                    "case_id": case_id,
                    "error": "No se encontró el chunk de jurisprudencia del caso.",
                }
            )
        for chunk in selected_jurisprudence:
            add_chunk(
                chunk,
                {
                    "relation_type": "case_jurisprudence",
                    "confidence": "high",
                    "evidence": {"case_id": case_id},
                },
            )

        for provenance in context.get("provenance_sources") or []:
            add_article(
                source_type=provenance.get("source_type"),
                raw_article_id=provenance.get("source_article_id"),
                relation_type="source_article_anchor",
                confidence="high",
                evidence=provenance,
            )

        context_unit = context.get("context_unit") or {}
        for norm in context_unit.get("applicable_norms") or []:
            norm_name = str(norm.get("norm_standardized") or "").strip().lower()
            source_type = NORM_NAME_TO_SOURCE.get(norm_name)
            if not source_type:
                continue
            for article_id in norm.get("articles") or []:
                add_article(
                    source_type=source_type,
                    raw_article_id=article_id,
                    relation_type="cited_in_jurisprudence",
                    confidence="medium",
                    evidence={
                        "norm_standardized": norm.get("norm_standardized"),
                        "norm_raw_text": norm.get("norm_raw_text"),
                    },
                )

        structured_rows = self.structured_by_url.get(normalize_url(context.get("entry_url")), [])
        for structured in structured_rows:
            for concordance in structured.get("page_concordances") or []:
                code = str(concordance.get("code") or "").strip().upper()
                source_type = CONCORDANCE_CODE_TO_SOURCE.get(code)
                if not source_type:
                    continue
                for article_id in concordance.get("articles") or []:
                    add_article(
                        source_type=source_type,
                        raw_article_id=article_id,
                        relation_type="page_concordance",
                        confidence="candidate",
                        evidence={
                            "code": code,
                            "entry_url": context.get("entry_url"),
                            "index_page_url": structured.get("page_source_url"),
                            "page_anchor_code": structured.get("page_anchor_code"),
                            "page_anchor_article_id": structured.get("page_anchor_article_id"),
                        },
                    )

        ordered = sorted(
            candidates.values(),
            key=lambda item: (
                0 if any(r["relation_type"] == "case_jurisprudence" for r in item["relations"]) else 1,
                item["candidate_id"],
            ),
        )
        return ResolutionResult(
            candidates=ordered,
            unresolved_references=unresolved,
            relation_counts=dict(sorted(relation_counts.items())),
        )


def candidates_for_prompt(result: ResolutionResult) -> list[dict[str, Any]]:
    """Vista explícita y compacta que se entrega al LLM."""
    output = []
    for candidate in result.candidates:
        chunk = candidate["chunk"]
        metadata = chunk.get("metadata") or {}
        output.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_type": chunk.get("source_type"),
                "title": chunk.get("title"),
                "article_id": metadata.get("article_id"),
                "resolution_reference": metadata.get("resolution_reference"),
                "relation_types": [r["relation_type"] for r in candidate["relations"]],
                "text": chunk.get("text"),
            }
        )
    return output


def validate_positive_candidate_ids(
    selected_ids: Iterable[str],
    result: ResolutionResult,
) -> list[str]:
    """Valida y deduplica la selección del LLM sin aceptar IDs inventados."""
    selected = list(dict.fromkeys(str(value) for value in selected_ids if value))
    if not selected:
        raise ValueError("La pregunta no seleccionó ningún positive_candidate_id.")
    unknown = sorted(set(selected) - result.candidate_ids)
    if unknown:
        raise ValueError(f"El LLM seleccionó candidate_ids inexistentes: {unknown}")
    return selected
