from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

SPIJ_BACKEND = "https://spijwsii.minjus.gob.pe/spij-ext-back/"


@dataclass
class SpijClient:
    session: requests.Session | None = None
    timeout: int = 60

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
        self._token: str | None = None

    def authenticate_guest(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token

        payload = {
            "usuario": "spijext",
            "clave": "password",
            "tipo": 0,
        }
        response = self.session.post(
            f"{SPIJ_BACKEND}authenticate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("value")
        if not token:
            raise RuntimeError(f"No se obtuvo token válido de SPIJ: {data}")
        self._token = token
        return token

    def get_norm_detail(self, norm_id: str) -> dict[str, Any]:
        token = self.authenticate_guest()
        response = self.session.get(
            f"{SPIJ_BACKEND}api/detallenorma/{norm_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if response.status_code == 401:
            token = self.authenticate_guest(force=True)
            response = self.session.get(
                f"{SPIJ_BACKEND}api/detallenorma/{norm_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()
