#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, UTC
from pathlib import Path

from legal_data.spij_client import SpijClient
from legal_data.storage import write_json, write_text


def main() -> None:
    norm_id = sys.argv[1] if len(sys.argv) > 1 else "H1141065"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/spij") / norm_id

    client = SpijClient()
    detail = client.get_norm_detail(norm_id)
    texto = detail.get("textoCompleto") or ""

    snapshot_meta = {
        "norm_id": norm_id,
        "fetched_at_utc": datetime.now(UTC).isoformat(),
        "codigoNorma": detail.get("codigoNorma"),
        "fechaPublicacion": detail.get("fechaPublicacion"),
        "sector": detail.get("sector"),
        "dispositivoLegal": detail.get("dispositivoLegal"),
        "textoCompleto_sha256": hashlib.sha256(texto.encode("utf-8", errors="replace")).hexdigest(),
        "textoCompleto_len": len(texto),
    }

    write_json(out_dir / "detail.json", detail)
    write_text(out_dir / "texto_completo.html", texto)
    write_json(out_dir / "snapshot_meta.json", snapshot_meta)

    print(json.dumps(snapshot_meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
