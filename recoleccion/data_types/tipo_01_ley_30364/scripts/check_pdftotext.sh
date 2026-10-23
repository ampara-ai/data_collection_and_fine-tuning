#!/usr/bin/env bash
set -euo pipefail
command -v pdftotext >/dev/null && echo "pdftotext: OK" || echo "pdftotext: MISSING"
