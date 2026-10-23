#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
TYPE_DIR = ROOT_DIR / "recoleccion" / "data_types" / "tipo_01_ley_30364"
SRC_DIR = TYPE_DIR / "src"
SCRIPTS_DIR = TYPE_DIR / "scripts"


def run_python_script(script_name: str, *args: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)
    cmd = ["uv", "run", "python", str(SCRIPTS_DIR / script_name), *args]
    subprocess.run(cmd, check=True, cwd=ROOT_DIR, env=env)


def cmd_collect(date_yyyymmdd: str | None) -> None:
    scan_date = date_yyyymmdd or datetime.now(UTC).strftime("%Y%m%d")
    print("[1/2] Bootstrap Ley 30364 desde SPIJ")
    run_python_script("bootstrap_law_30364.py")

    print(f"[2/2] Escaneo exploratorio El Peruano para fecha: {scan_date}")
    run_python_script("daily_elperuano_scan.py", scan_date)


def cmd_worker() -> None:
    print("Iniciando worker para Ley 30364...")
    run_python_script("run_daily_worker_loop.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Entrypoint reproducible para la fase de recolección (tipo de dato 01: Ley 30364)."
    )
    subparsers = parser.add_subparsers(dest="command")

    collect_parser = subparsers.add_parser(
        "collect",
        help="Ejecuta bootstrap + escaneo exploratorio de recolección.",
    )
    collect_parser.add_argument(
        "date",
        nargs="?",
        help="Fecha en formato YYYYMMDD para el escaneo de El Peruano.",
    )

    subparsers.add_parser(
        "worker",
        help="Inicia el worker en bucle para la fase de recolección.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args.date)
    elif args.command == "worker":
        cmd_worker()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
