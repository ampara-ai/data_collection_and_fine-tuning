#!/usr/bin/env python3
"""Sonda mínima para Búsquedas El Peruano vía GraphQL.

Meta: reproducir con código el descubrimiento del endpoint de búsqueda
que usa el frontend y devolver metadata cruda de publicaciones.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests

GRAPHQL_URL = "https://busquedas.elperuano.pe/api/graphql"

GENERIC_QUERY = """
query Generic(
  $fechaIni: String
  $fechaFin: String
  $institucion: String
  $op: String
  $paginatedBy: Int
  $query: String
  $start: Int
  $tipoDispositivo: String
  $tipoPublicacion: String
  $ci: String
) {
  results:getGenericPublication(
    fechaIni: $fechaIni
    fechaFin: $fechaFin
    institucion: $institucion
    op: $op
    paginatedBy: $paginatedBy
    query: $query
    start: $start
    tipoDispositivo: $tipoDispositivo
    tipoPublicacion: $tipoPublicacion
    ci: $ci
  ) {
    totalHits
    start
    hasNext
    paginatedBy
    hits {
      clasificacion1
      clasificacion2
      fechaPublicacion
      nombreDispositivo
      op
      paginas
      rubro
      sector
      sumilla
      tipoDispositivo
      tipoPublicacion
      urlPDF
      urlPortada
    }
  }
}
""".strip()


def search_publications(variables: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        GRAPHQL_URL,
        json={
            "query": GENERIC_QUERY,
            "variables": variables,
            "operationName": "Generic",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    # Fecha default de demostración: 2025-09-14, porque ahí vimos un caso útil
    # en la investigación manual.
    date_yyyymmdd = sys.argv[1] if len(sys.argv) > 1 else "20250914"
    tipo_dispositivo = sys.argv[2] if len(sys.argv) > 2 else "RESOLUCION MINISTERIAL"

    payload = {
        "fechaIni": date_yyyymmdd,
        "fechaFin": date_yyyymmdd,
        "tipoPublicacion": "NL",
        "tipoDispositivo": tipo_dispositivo,
        "start": 0,
        "ci": "ONLY",
    }

    data = search_publications(payload)
    results = data["data"]["results"]
    print(
        json.dumps(
            {
                "query": payload,
                "totalHits": results["totalHits"],
                "hasNext": results["hasNext"],
                "sample": results["hits"][:3],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
