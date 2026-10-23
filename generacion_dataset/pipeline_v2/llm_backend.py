"""Backends de LLM con una interfaz común: openrouter | session | mock.

* openrouter: llama a la API (OpenAI SDK contra OpenRouter) y guarda cada respuesta en work/<paso>/responses/.
* session:    NO llama a ninguna API. Escribe cada petición en work/<paso>/requests/<task_id>.json y espera que
              alguien (p. ej. una sesión de Claude Code con subagentes) deje la respuesta en
              work/<paso>/responses/<task_id>.json. Al volver a ejecutar el paso, lee esas respuestas.
* mock:       respuestas sintéticas para probar el flujo de punta a punta (no sirve como datos).

Los tres comparten la caché work/<paso>/responses/: un paso es reanudable y se puede alternar de backend.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from common import read_json, write_json


class PendingResponse(Exception):
    """Falta la respuesta de una tarea (modo session)."""


def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ValueError(f"La respuesta no contiene JSON: {text[:200]!r}")
        return json.loads(m.group(0))


class Backend:
    def __init__(self, kind: str, step: str, out_dir: Path, model: str, temperature: float = 0.3,
                 max_tokens: int = 8000, mock_fn: Callable[[str, dict], dict] | None = None, retries: int = 3):
        if kind not in ("openrouter", "session", "mock"):
            raise ValueError(f"backend desconocido: {kind}")
        self.kind, self.model, self.temperature, self.max_tokens = kind, model, temperature, max_tokens
        self.mock_fn, self.retries = mock_fn, retries
        out_dir = Path(out_dir).resolve()
        self.req_dir = out_dir / "work" / step / "requests"
        self.res_dir = out_dir / "work" / step / "responses"
        self.req_dir.mkdir(parents=True, exist_ok=True)
        self.res_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._lock = threading.Lock()
        self.usage = {"calls": 0, "cached": 0}

    # -- API
    def _openrouter(self):
        if self._client is None:
            from dotenv import load_dotenv
            from openai import OpenAI
            from config import REPO
            load_dotenv(REPO / ".env")
            load_dotenv()
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError("Falta OPENROUTER_API_KEY (variable de entorno o .env)")
            self._client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        return self._client

    def complete_json(self, task_id: str, system: str, user: str, meta: dict | None = None) -> dict:
        res_path = self.res_dir / f"{task_id}.json"
        if res_path.exists():
            with self._lock:
                self.usage["cached"] += 1
            return read_json(res_path)

        if self.kind == "session":
            req_path = self.req_dir / f"{task_id}.json"
            if not req_path.exists():
                write_json(req_path, {"task_id": task_id, "system": system, "user": user, "meta": meta or {},
                                      "write_response_to": str(res_path.resolve())})
            raise PendingResponse(task_id)

        if self.kind == "mock":
            out = self.mock_fn(task_id, meta or {})
        else:
            out = self._call_api(system, user)
        with self._lock:
            self.usage["calls"] += 1
        write_json(res_path, out)
        return out

    def _call_api(self, system: str, user: str) -> dict:
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                r = self._openrouter().chat.completions.create(
                    model=self.model, temperature=self.temperature, max_tokens=self.max_tokens,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                )
                content = r.choices[0].message.content
                if not content:
                    raise ValueError("respuesta vacía")
                return extract_json(content)
            except Exception as exc:  # reintento con espera creciente
                last = exc
                time.sleep(2 * attempt)
        raise RuntimeError(f"falló la llamada tras {self.retries} intentos: {last}")


def run_tasks(tasks: list, handler: Callable, backend: Backend, workers: int = 4) -> tuple[list, list, list]:
    """Ejecuta handler(task) para cada tarea. Devuelve (resultados, pendientes, errores)."""
    results, pending, errors = [], [], []

    def one(t):
        try:
            return ("ok", handler(t))
        except PendingResponse as p:
            return ("pending", str(p))
        except Exception as exc:  # noqa: BLE001 - se informa por tarea
            return ("error", f"{type(exc).__name__}: {exc}")

    if backend.kind == "openrouter" and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(one, t): t for t in tasks}
            for fut in as_completed(futs):
                kind, val = fut.result()
                {"ok": results, "pending": pending, "error": errors}[kind].append(val if kind != "error" else (futs[fut], val))
    else:
        for t in tasks:
            kind, val = one(t)
            {"ok": results, "pending": pending, "error": errors}[kind].append(val if kind != "error" else (t, val))
    return results, pending, errors


def finish(step: str, backend: Backend, pending: list, errors: list) -> None:
    """Resumen final del paso; sale con código 3 si faltan respuestas (modo session) y 1 si hubo errores."""
    print(f"[{step}] backend={backend.kind} llamadas={backend.usage['calls']} en caché={backend.usage['cached']} "
          f"pendientes={len(pending)} errores={len(errors)}")
    for t, msg in errors[:10]:
        print(f"   [error] {t if isinstance(t, str) else t.get('task_id', t)}: {msg}")
    if pending:
        print(f"   Faltan {len(pending)} respuestas. Peticiones en: {backend.req_dir}\n"
              f"   Deja cada respuesta (solo el JSON) en: {backend.res_dir}/<task_id>.json y vuelve a ejecutar el paso.")
        sys.exit(3)
    if errors:
        sys.exit(1)
