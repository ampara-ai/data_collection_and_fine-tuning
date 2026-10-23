from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class ElPeruanoClient:
    session: requests.Session | None = None
    timeout: int = 60

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    def search_publications(self, *, fecha_ini: str, fecha_fin: str, tipo_publicacion: str = "NL", tipo_dispositivo: str | None = None, query: str | None = None, start: int = 0, ci: str = "ONLY", paginated_by: int | None = None, institucion: str | None = None, op: str | None = None) -> dict[str, Any]:
        variables: dict[str, Any] = {
            "fechaIni": fecha_ini,
            "fechaFin": fecha_fin,
            "tipoPublicacion": tipo_publicacion,
            "tipoDispositivo": tipo_dispositivo,
            "query": query,
            "start": start,
            "ci": ci,
        }
        if paginated_by is not None:
            variables["paginatedBy"] = paginated_by
        if institucion is not None:
            variables["institucion"] = institucion
        if op is not None:
            variables["op"] = op
        response = self.session.post(
            GRAPHQL_URL,
            json={
                "query": GENERIC_QUERY,
                "variables": variables,
                "operationName": "Generic",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"]["results"]

    def download_pdf(self, url: str) -> bytes:
        response = self.session.get(url, timeout=max(self.timeout, 120))
        response.raise_for_status()
        return response.content
