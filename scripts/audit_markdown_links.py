#!/usr/bin/env python3
"""Comprueba que los enlaces Markdown locales apunten a rutas existentes."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXCLUDED_PARTS = {".git", ".venv", "__pycache__"}


def main() -> None:
    broken: list[dict[str, str]] = []
    markdown_files = [
        path
        for path in REPO_ROOT.rglob("*.md")
        if not EXCLUDED_PARTS.intersection(path.parts)
    ]

    for markdown_path in markdown_files:
        content = markdown_path.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(content):
            if "://" in raw_target or raw_target.startswith(("#", "mailto:", "<")):
                continue
            target = raw_target.split("#", 1)[0]
            if not target:
                continue
            resolved = (markdown_path.parent / target).resolve()
            if not resolved.exists():
                broken.append(
                    {
                        "document": str(markdown_path.relative_to(REPO_ROOT)),
                        "target": raw_target,
                    }
                )

    report = {
        "check_type": "local_markdown_links",
        "status": "ok" if not broken else "error",
        "markdown_files": len(markdown_files),
        "broken_links": broken,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if broken:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
