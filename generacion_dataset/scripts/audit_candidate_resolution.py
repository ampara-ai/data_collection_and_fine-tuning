#!/usr/bin/env python3
"""Comprueba la resolución de candidatos sin ejecutar modelos generativos."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from legal_candidate_resolver import RESOLVER_VERSION, LegalCandidateResolver, candidates_for_prompt
from generate_colloquial_legal_questions import (
    build_bm25,
    build_negative_candidate_pool,
    extract_case_payload_for_llm,
    merge_corpus_chunks,
    negative_candidates_for_prompt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent

DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "input" / "document_chunks_all.jsonl"
DEFAULT_CASES_DIR = PROJECT_ROOT / "data" / "intermediate" / "resumeai_batch" / "cases"
DEFAULT_ELIGIBLE_CASES_MANIFEST = REPO_ROOT / "entrenamiento" / "data" / "split_manifest.json"
DEFAULT_CONTEXT_UNITS_PATH = PROJECT_ROOT / "data" / "input" / "jurisprudence_context_units.json"
DEFAULT_CP_ARTICLES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_02_codigo_penal" / "data" / "processed" / "all_articles.json"
DEFAULT_CPP_ARTICLES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "all_articles.json"
DEFAULT_LEY_30364_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_01_ley_30364" / "data" / "processed" / "law_30364_structured.json"
DEFAULT_STRUCTURED_ENTRIES_PATH = REPO_ROOT / "recoleccion" / "data_types" / "tipo_04_jurisprudencia" / "data" / "processed" / "jurisprudence_entries_structured.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def case_info_from_file(path: Path) -> tuple[str, bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pdf_filename = (data.get("source_trace") or {}).get("pdf_filename")
    case_id = Path(pdf_filename).stem if pdf_filename else path.stem
    is_candidate = (data.get("factual_density_signals") or {}).get("is_dataset_candidate", True)
    return case_id, bool(is_candidate)


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    return ordered[round((len(ordered) - 1) * fraction)]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    resolver = LegalCandidateResolver.from_paths(
        cp_articles_path=args.cp_articles_path,
        cpp_articles_path=args.cpp_articles_path,
        ley_30364_path=args.ley_30364_path,
        context_units_path=args.context_units_path,
        structured_entries_path=args.structured_entries_path,
    )
    snapshot_chunks = load_jsonl(args.chunks_path)
    effective_chunks = merge_corpus_chunks(snapshot_chunks, resolver.all_article_chunks())
    bm25_index = build_bm25(effective_chunks)
    jurisprudence_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in effective_chunks:
        if chunk.get("source_type") != "tipo_04_jurisprudencia":
            continue
        doc_id = str(chunk.get("doc_id") or "")
        if doc_id.startswith("tipo04_"):
            jurisprudence_by_case[doc_id.removeprefix("tipo04_")].append(chunk)

    case_paths = sorted(args.cases_dir.glob("*.json"))
    case_info = [case_info_from_file(path) for path in case_paths]
    case_path_by_id = {
        case_id: path
        for path, (case_id, _) in zip(case_paths, case_info, strict=True)
    }
    if case_info:
        eligible_case_ids = [case_id for case_id, is_candidate in case_info if is_candidate]
        skipped_not_candidate = sum(not is_candidate for _, is_candidate in case_info)
        case_id_source = "resumeai_case_files"
    else:
        split_manifest = json.loads(args.eligible_cases_manifest.read_text(encoding="utf-8"))
        eligible_case_ids = sorted(
            {
                str(case_id)
                for key in ("train_cases", "test_cases")
                for case_id in split_manifest.get(key, [])
            }
        )
        skipped_not_candidate = 0
        case_id_source = "split_manifest_fallback"

    if args.case_id:
        known_case_ids = {case_id for case_id, _ in case_info} or set(eligible_case_ids)
        if args.case_id not in known_case_ids:
            raise ValueError(f"No existe el case_id solicitado: {args.case_id}")
        case_ids = [args.case_id]
        skipped_not_candidate = 0
    else:
        case_ids = eligible_case_ids

    relation_totals: Counter[str] = Counter()
    unresolved_by_relation: Counter[str] = Counter()
    candidate_counts: list[int] = []
    negative_pool_counts: list[int] = []
    prompt_sizes: list[int] = []
    case_reports: list[dict[str, Any]] = []

    for case_id in case_ids:
        result = resolver.resolve_case(case_id, jurisprudence_by_case.get(case_id, []))
        relation_totals.update(result.relation_counts)
        unresolved_by_relation.update(
            str(item.get("relation_type") or "unknown")
            for item in result.unresolved_references
        )
        prompt_view = candidates_for_prompt(result)
        case_path = case_path_by_id.get(case_id)
        if case_path is None:
            negative_pool = []
        else:
            case_payload = extract_case_payload_for_llm(
                json.loads(case_path.read_text(encoding="utf-8"))
            )
            negative_pool = build_negative_candidate_pool(
                bm25_index=bm25_index,
                case_payload=case_payload,
                candidate_result=result,
            )
        negative_prompt_view = negative_candidates_for_prompt(negative_pool)
        candidate_counts.append(len(prompt_view))
        negative_pool_counts.append(len(negative_prompt_view))
        prompt_sizes.append(
            len(json.dumps(prompt_view, ensure_ascii=False))
            + len(json.dumps(negative_prompt_view, ensure_ascii=False))
        )
        if args.case_id:
            case_report = result.as_dict(case_id)
            case_report["negative_candidate_pool"] = negative_pool
            case_reports.append(case_report)

    coverage: dict[str, dict[str, Any]] = {}
    relation_names = {
        key.removesuffix("_references_total")
        for key in relation_totals
        if key.endswith("_references_total")
    }
    for relation in sorted(relation_names):
        total = relation_totals[f"{relation}_references_total"]
        resolved = relation_totals[f"{relation}_references_resolved"]
        coverage[relation] = {
            "references_total": total,
            "references_resolved": resolved,
            "coverage_percent": round(100 * resolved / total, 2) if total else None,
            "candidate_edges": relation_totals[f"{relation}_candidate_edges"],
        }

    report: dict[str, Any] = {
        "check_type": "deterministic_candidate_resolution_no_llm",
        "resolver_version": RESOLVER_VERSION,
        "case_id_source": case_id_source,
        "case_count": len(case_ids),
        "case_count_skipped_not_dataset_candidate": skipped_not_candidate,
        "source_files": resolver.source_files_summary(),
        "coverage_by_relation": coverage,
        "unresolved_by_relation": dict(sorted(unresolved_by_relation.items())),
        "candidate_set_size": {
            "min": min(candidate_counts, default=0),
            "median": statistics.median(candidate_counts) if candidate_counts else 0,
            "p90": percentile(candidate_counts, 0.9),
            "max": max(candidate_counts, default=0),
        },
        "negative_candidate_pool_size": {
            "min": min(negative_pool_counts, default=0),
            "median": statistics.median(negative_pool_counts) if negative_pool_counts else 0,
            "p90": percentile(negative_pool_counts, 0.9),
            "max": max(negative_pool_counts, default=0),
        },
        "serialized_prompt_characters": {
            "median": statistics.median(prompt_sizes) if prompt_sizes else 0,
            "p90": percentile(prompt_sizes, 0.9),
            "max": max(prompt_sizes, default=0),
        },
    }
    if args.case_id:
        report["cases"] = case_reports
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mide cobertura y muestra candidatos sin llamar al LLM ni modificar datasets."
    )
    parser.add_argument("--case-id", help="Limita el informe a un caso e incluye sus candidatos.")
    parser.add_argument("--json-output", type=Path, help="Opcional: guarda también el informe JSON.")
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument(
        "--eligible-cases-manifest",
        type=Path,
        default=DEFAULT_ELIGIBLE_CASES_MANIFEST,
        help="Fallback versionado con train_cases/test_cases cuando no están los JSON de ResumeAI.",
    )
    parser.add_argument("--cp-articles-path", type=Path, default=DEFAULT_CP_ARTICLES_PATH)
    parser.add_argument("--cpp-articles-path", type=Path, default=DEFAULT_CPP_ARTICLES_PATH)
    parser.add_argument("--ley-30364-path", type=Path, default=DEFAULT_LEY_30364_PATH)
    parser.add_argument("--context-units-path", type=Path, default=DEFAULT_CONTEXT_UNITS_PATH)
    parser.add_argument("--structured-entries-path", type=Path, default=DEFAULT_STRUCTURED_ENTRIES_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
