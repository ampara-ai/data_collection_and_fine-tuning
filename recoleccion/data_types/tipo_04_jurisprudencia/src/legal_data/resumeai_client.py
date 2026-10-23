from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field


class ResumeAILegalAnalysisRequest(BaseModel):
    pdf_path: str | Path
    source_url: str | None = None
    title: str | None = None
    resolution_reference_raw: str | None = None
    jurisprudence_type: str | None = None
    verbose: bool = False
    similarity_threshold: float = 0.85


class ResumeAILegalRunMetadata(BaseModel):
    status: Literal["success", "error"]
    run_id: str | None = None
    source_url: str | None = None
    title: str | None = None
    resolution_reference_raw: str | None = None
    jurisprudence_type: str | None = None
    pdf_filename: str
    pdf_sha256: str
    api_base_url: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResumeAILegalEnrichedCase(BaseModel):
    source_trace: dict[str, Any]
    resumeai_run: ResumeAILegalRunMetadata
    report: dict[str, Any]
    metrics: dict[str, Any]
    factual_density_signals: dict[str, Any]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_factual_density_signals(report: dict[str, Any]) -> dict[str, Any]:
    legal = report.get("legal_analysis", {}) or {}

    case_background = legal.get("case_background", []) or []
    reported_acts = legal.get("reported_acts", []) or []
    evidence_summary = legal.get("evidence_summary", []) or []
    legal_reasoning = legal.get("legal_reasoning", []) or []
    outcomes = legal.get("prosecutorial_or_procedural_outcomes", []) or []
    norms = legal.get("norms_cited", []) or []

    score = 0
    if case_background:
        score += 1
    if reported_acts:
        score += 2
    if evidence_summary:
        score += 2
    if legal_reasoning:
        score += 1
    if outcomes:
        score += 1
    if len(norms) >= 2:
        score += 1

    return {
        "has_case_background": bool(case_background),
        "has_reported_acts": bool(reported_acts),
        "has_evidence_summary": bool(evidence_summary),
        "has_legal_reasoning": bool(legal_reasoning),
        "has_procedural_outcomes": bool(outcomes),
        "norms_count": len(norms),
        "factual_richness_score": score,
        "is_fact_rich_minimum": bool(case_background and reported_acts),
        "is_dataset_candidate": bool(score >= 4 and case_background and reported_acts),
    }


def analyze_pdf_with_resumeai_legal(
    request: ResumeAILegalAnalysisRequest,
    *,
    api_base_url: str = "http://127.0.0.1:8000",
    timeout_sec: int = 1800,
) -> ResumeAILegalEnrichedCase:
    pdf_path = Path(request.pdf_path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    endpoint = f"{api_base_url.rstrip('/')}/analyze"
    with pdf_path.open("rb") as f:
        response = requests.post(
            endpoint,
            files={"file": (pdf_path.name, f, "application/pdf")},
            data={
                "verbose": str(request.verbose).lower(),
                "similarity_threshold": str(request.similarity_threshold),
            },
            timeout=timeout_sec,
        )

    response.raise_for_status()
    payload = response.json()

    report = payload.get("report", {}) or {}
    metrics = payload.get("metrics", {}) or {}
    warnings = payload.get("warnings", []) or []
    errors = payload.get("errors", []) or []

    return ResumeAILegalEnrichedCase(
        source_trace={
            "source_url": request.source_url,
            "title": request.title,
            "resolution_reference_raw": request.resolution_reference_raw,
            "jurisprudence_type": request.jurisprudence_type,
            "pdf_filename": pdf_path.name,
        },
        resumeai_run=ResumeAILegalRunMetadata(
            status=payload.get("status", "success"),
            run_id=payload.get("run_id"),
            source_url=request.source_url,
            title=request.title,
            resolution_reference_raw=request.resolution_reference_raw,
            jurisprudence_type=request.jurisprudence_type,
            pdf_filename=pdf_path.name,
            pdf_sha256=_sha256_file(pdf_path),
            api_base_url=api_base_url,
            warnings=warnings,
            errors=errors,
        ),
        report=report,
        metrics=metrics,
        factual_density_signals=_build_factual_density_signals(report),
    )


def persist_enriched_case(
    enriched_case: ResumeAILegalEnrichedCase,
    *,
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(enriched_case.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
