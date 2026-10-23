#!/usr/bin/env python3
"""Exploración mínima del backend público de SPIJ libre.

Este script documenta el flujo observado en la app web pública:
1. obtener token guest
2. pedir detalle de una norma por ID

Por ahora está pensado como script de investigación/reproducción, no todavía como cliente final de producción.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests

SPIJ_BACKEND = "https://spijwsii.minjus.gob.pe/spij-ext-back/"


def authenticate_guest(session: requests.Session) -> str:
    """Obtiene token de acceso libre observado en el frontend público."""
    payload = {
        "usuario": "spijext",
        "clave": "password",
        "tipo": 0,
    }
    response = session.post(f"{SPIJ_BACKEND}authenticate", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    token = data.get("value")
    if not token:
        raise RuntimeError(f"No se obtuvo token válido: {data}")
    return token


def fetch_norm_detail(session: requests.Session, norm_id: str, token: str) -> dict[str, Any]:
    """Pide el detalle JSON de una norma pública por ID."""
    response = session.get(
        f"{SPIJ_BACKEND}api/detallenorma/{norm_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    norm_id = sys.argv[1] if len(sys.argv) > 1 else "H1141065"
    session = requests.Session()

    token = authenticate_guest(session)
    detail = fetch_norm_detail(session, norm_id, token)

    summary = {
        "id": detail.get("id"),
        "codigoNorma": detail.get("codigoNorma"),
        "fechaPublicacion": detail.get("fechaPublicacion"),
        "sector": detail.get("sector"),
        "dispositivoLegal": detail.get("dispositivoLegal"),
        "textoCompleto_len": len(detail.get("textoCompleto") or ""),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
