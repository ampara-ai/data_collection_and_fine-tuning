#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RECOLECCION_DIR = ROOT_DIR / "recoleccion"


def run_python(script_path: Path, cwd: Path, extra_env: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    cmd = ["uv", "run", "python", str(script_path)]
    subprocess.run(cmd, check=True, cwd=cwd, env=env)


def cmd_plan() -> None:
    print("Pipeline base documental unificado")
    print("[1] tipo_01_ley_30364 -> normalización por artículos")
    print("[2] tipo_02_codigo_penal -> normalización por artículos")
    print("[3] tipo_03_codigo_procesal_penal -> normalización por artículos")
    print("[4] tipo_04_jurisprudencia -> fetch detail + resumen base documental por entry")
    print("[5] tipo_05_documentos_institucionales -> normalización por sección/bloque")
    print("[6] chunking unificado + consolidación global")
    print("\nImplementado ahora mismo:")
    print("- tipo_01 normalize/chunk")
    print("- tipo_02 normalize/chunk")
    print("- tipo_03 normalize/chunk")
    print("- tipo_04 normalize/chunk")
    print("- tipo_05 normalize/chunk")
    print("\nVer esquema: recoleccion/docs/unified-normalization-schema.md")


def cmd_tipo04_sample10() -> None:
    type_dir = RECOLECCION_DIR / "data_types" / "tipo_04_jurisprudencia"
    src_dir = type_dir / "src"
    script_path = type_dir / "run_sample_10_pipeline.py"
    run_python(script_path=script_path, cwd=type_dir, extra_env={"PYTHONPATH": str(src_dir)})


def cmd_tipo04_build_seeds() -> None:
    _run_type_script("tipo_04_jurisprudencia", "build_seed_urls_from_tipo_02_03.py")


def cmd_tipo04_fetch_indexes() -> None:
    _run_type_script("tipo_04_jurisprudencia", "fetch_all_index_pages.py")


def cmd_tipo04_parse_entries() -> None:
    _run_type_script("tipo_04_jurisprudencia", "llm_parse_index_entries.py")
    _run_type_script("tipo_04_jurisprudencia", "dedupe_entries.py")


def cmd_tipo04_resolve_content() -> None:
    _run_type_script("tipo_04_jurisprudencia", "resolve_entry_content.py")


def cmd_tipo04_summarize() -> None:
    _run_type_script("tipo_04_jurisprudencia", "llm_summarize_jurisprudence.py")


def cmd_tipo04_build_contextual_chunks() -> None:
    _run_type_script("tipo_04_jurisprudencia", "build_contextual_chunks.py")


def cmd_tipo04_normalize() -> None:
    type_dir = RECOLECCION_DIR / "data_types" / "tipo_04_jurisprudencia"
    src_dir = type_dir / "src"
    script_path = type_dir / "scripts" / "build_normalized_documents.py"
    run_python(script_path=script_path, cwd=type_dir, extra_env={"PYTHONPATH": str(src_dir)})


def cmd_tipo04_chunk() -> None:
    type_dir = RECOLECCION_DIR / "data_types" / "tipo_04_jurisprudencia"
    src_dir = type_dir / "src"
    script_path = type_dir / "scripts" / "build_document_chunks.py"
    run_python(script_path=script_path, cwd=type_dir, extra_env={"PYTHONPATH": str(src_dir)})


def _run_type_script(relative_type_dir: str, script_name: str) -> None:
    type_dir = RECOLECCION_DIR / "data_types" / relative_type_dir
    src_dir = type_dir / "src"
    script_path = type_dir / "scripts" / script_name
    run_python(script_path=script_path, cwd=type_dir, extra_env={"PYTHONPATH": str(src_dir)})


def cmd_tipo01_normalize() -> None:
    _run_type_script("tipo_01_ley_30364", "build_normalized_documents.py")


def cmd_tipo01_chunk() -> None:
    _run_type_script("tipo_01_ley_30364", "build_document_chunks.py")


def cmd_tipo02_normalize() -> None:
    _run_type_script("tipo_02_codigo_penal", "build_normalized_documents.py")


def cmd_tipo02_chunk() -> None:
    _run_type_script("tipo_02_codigo_penal", "build_document_chunks.py")


def cmd_tipo03_normalize() -> None:
    _run_type_script("tipo_03_codigo_procesal_penal", "build_normalized_documents.py")


def cmd_tipo03_chunk() -> None:
    _run_type_script("tipo_03_codigo_procesal_penal", "build_document_chunks.py")


def cmd_tipo05_normalize() -> None:
    _run_type_script("tipo_05_documentos_institucionales", "build_normalized_documents.py")


def cmd_tipo05_chunk() -> None:
    _run_type_script("tipo_05_documentos_institucionales", "build_document_chunks.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Entrypoint reproducible desde recoleccion/ para el pipeline base documental."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("plan", help="Muestra el orden del pipeline base documental unificado.")
    subparsers.add_parser(
        "tipo01-normalize",
        help="Construye normalized_documents.jsonl para tipo_01_ley_30364 desde snapshot SPIJ.",
    )
    subparsers.add_parser(
        "tipo01-chunk",
        help="Construye document_chunks.jsonl para tipo_01_ley_30364.",
    )
    subparsers.add_parser(
        "tipo02-normalize",
        help="Construye normalized_documents.jsonl para tipo_02_codigo_penal.",
    )
    subparsers.add_parser(
        "tipo02-chunk",
        help="Construye document_chunks.jsonl para tipo_02_codigo_penal.",
    )
    subparsers.add_parser(
        "tipo03-normalize",
        help="Construye normalized_documents.jsonl para tipo_03_codigo_procesal_penal.",
    )
    subparsers.add_parser(
        "tipo03-chunk",
        help="Construye document_chunks.jsonl para tipo_03_codigo_procesal_penal.",
    )
    subparsers.add_parser(
        "tipo04-sample10",
        help="Ejecuta la muestra reproducible de 10 índices de tipo_04_jurisprudencia desde la raíz de recoleccion.",
    )
    subparsers.add_parser("tipo04-build-seeds", help="Construye seeds globales de jurisprudencia desde tipo_02 y tipo_03.")
    subparsers.add_parser("tipo04-fetch-indexes", help="Descarga todos los índices de jurisprudencia seed.")
    subparsers.add_parser("tipo04-parse-entries", help="Parsea con LLM los entries de todos los índices y deduplica.")
    subparsers.add_parser("tipo04-resolve-content", help="Resuelve contenido textual por entry de jurisprudencia.")
    subparsers.add_parser("tipo04-summarize", help="Sintetiza por LLM los entries de jurisprudencia para retrieval.")
    subparsers.add_parser("tipo04-build-contextual-chunks", help="Construye chunks contextuales finales de tipo_04.")
    subparsers.add_parser(
        "tipo04-normalize",
        help="Construye normalized_documents.jsonl para tipo_04 desde los detail pages ya recolectados.",
    )
    subparsers.add_parser(
        "tipo04-chunk",
        help="Construye document_chunks.jsonl para tipo_04 desde normalized_documents.jsonl.",
    )
    subparsers.add_parser(
        "tipo05-normalize",
        help="Construye normalized_documents.jsonl para tipo_05_documentos_institucionales.",
    )
    subparsers.add_parser(
        "tipo05-chunk",
        help="Construye document_chunks.jsonl para tipo_05_documentos_institucionales.",
    )
    subparsers.add_parser(
        "consolidate-chunks",
        help="Consolida los document_chunks.jsonl de todos los tipos en una salida global.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan()
        return
    if args.command == "tipo01-normalize":
        cmd_tipo01_normalize()
        return
    if args.command == "tipo01-chunk":
        cmd_tipo01_chunk()
        return
    if args.command == "tipo02-normalize":
        cmd_tipo02_normalize()
        return
    if args.command == "tipo02-chunk":
        cmd_tipo02_chunk()
        return
    if args.command == "tipo03-normalize":
        cmd_tipo03_normalize()
        return
    if args.command == "tipo03-chunk":
        cmd_tipo03_chunk()
        return
    if args.command == "tipo04-sample10":
        cmd_tipo04_sample10()
        return
    if args.command == "tipo04-build-seeds":
        cmd_tipo04_build_seeds()
        return
    if args.command == "tipo04-fetch-indexes":
        cmd_tipo04_fetch_indexes()
        return
    if args.command == "tipo04-parse-entries":
        cmd_tipo04_parse_entries()
        return
    if args.command == "tipo04-resolve-content":
        cmd_tipo04_resolve_content()
        return
    if args.command == "tipo04-summarize":
        cmd_tipo04_summarize()
        return
    if args.command == "tipo04-build-contextual-chunks":
        cmd_tipo04_build_contextual_chunks()
        return
    if args.command == "tipo04-normalize":
        cmd_tipo04_normalize()
        return
    if args.command == "tipo04-chunk":
        cmd_tipo04_chunk()
        return
    if args.command == "tipo05-normalize":
        cmd_tipo05_normalize()
        return
    if args.command == "tipo05-chunk":
        cmd_tipo05_chunk()
        return
    if args.command == "consolidate-chunks":
        run_python(script_path=RECOLECCION_DIR / "scripts" / "consolidate_document_chunks.py", cwd=RECOLECCION_DIR)
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
