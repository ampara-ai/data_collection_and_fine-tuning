"""Utilidades compartidas del pipeline v2: E/S, tokenización, solapamiento léxico, grupos de chunks idénticos, BM25."""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

STOP = set(
    "a al algo ante aunque con como cada cual cuando cuanto cuantos de del donde el ella ellos en entre era es esa ese "
    "eso esta este esto estoy fue ha han hasta hay la las le les lo los me mi mis mucho muy no nos o otra otro para "
    "pero por porque que quien quiero se si sin sobre solo son su sus te tengo tiene tienen todo un una uno unos y ya "
    "yo puedo puede pueden hace hacer hago voy va ser sea tener tan tras desde dentro".split()
)


# ---------------------------------------------------------------- E/S
def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- texto
def norm_tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9ñ]+", t)


def content_tokens(text: str) -> list[str]:
    return [w for w in norm_tokens(text) if w not in STOP and len(w) > 2]


def lexical_overlap(query: str, chunk_text: str) -> float:
    """Fracción de palabras de contenido de la pregunta que aparecen en el chunk (misma definición que unseen)."""
    q, c = set(content_tokens(query)), set(content_tokens(chunk_text))
    return len(q & c) / max(1, len(q))


def jaccard(a: str, b: str) -> float:
    a, b = set(content_tokens(a)), set(content_tokens(b))
    return len(a & b) / max(1, len(a | b))


def content_key(text: str) -> str:
    """Clave de contenido: dos chunks con el mismo texto (p. ej. un artículo repetido en dos tipos de fuente)."""
    return hashlib.sha256(" ".join(norm_tokens(text)).encode("utf-8")).hexdigest()[:16]


def stable_unit(*parts: object) -> float:
    """Número determinista en [0, 1) a partir de strings; no depende del orden ni del tamaño del corpus."""
    h = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


# ---------------------------------------------------------------- corpus
def source_code(chunk: dict) -> str:
    """'01'..'05' a partir de source_type (tipo_01_ley_30364 -> '01')."""
    m = re.match(r"tipo_(\d+)", str(chunk.get("source_type") or ""))
    return m.group(1) if m else "??"


def article_base(chunk: dict) -> tuple[str, str] | None:
    """(source_type, número base del artículo): 22-A y 22 comparten base. None si no es un artículo numerado."""
    aid = str((chunk.get("metadata") or {}).get("article_id") or "")
    m = re.match(r"(\d+)", aid)
    if m and chunk.get("source_type") in ("tipo_01_ley_30364", "tipo_02_codigo_penal", "tipo_03_codigo_procesal_penal"):
        return (chunk["source_type"], m.group(1))
    return None


def load_corpus(path: Path) -> dict[str, dict]:
    chunks = read_jsonl(path)
    ids = [c["chunk_id"] for c in chunks]
    if len(ids) != len(set(ids)):
        dup = [k for k, v in Counter(ids).items() if v > 1][:5]
        raise ValueError(f"chunk_id duplicados en el corpus: {dup}")
    return {c["chunk_id"]: c for c in chunks}


def groups_by_content(corpus: dict[str, dict]) -> dict[str, list[str]]:
    """content_key -> [chunk_id, ...] (sólo chunks con texto idéntico quedan en el mismo grupo)."""
    g: dict[str, list[str]] = {}
    for cid, c in corpus.items():
        g.setdefault(content_key(c.get("text") or ""), []).append(cid)
    return {k: sorted(v) for k, v in g.items()}


def near_duplicate_groups(corpus: dict[str, dict], threshold: float = 0.85) -> dict[str, list[str]]:
    """Agrupa chunks de contenido (casi) idéntico: mismo texto exacto o Jaccard de palabras >= threshold
    (p. ej. un artículo del Código Penal repetido dentro de la Ley 30364 con otra puntuación).
    Devuelve group_key -> [chunk_id, ...] (todos los chunks aparecen, los únicos en grupos de uno)."""
    ids = sorted(corpus)
    toks = {i: frozenset(content_tokens(corpus[i].get("text") or "")) for i in ids}
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # índice invertido por palabra rara para no comparar los ~N^2 pares
    inv: dict[str, list[str]] = {}
    for i in ids:
        for w in toks[i]:
            inv.setdefault(w, []).append(i)
    for i in ids:
        if not toks[i]:
            continue
        cand: Counter = Counter()
        for w in toks[i]:
            lst = inv[w]
            if len(lst) <= 40:                 # ignora palabras que están en casi todo el corpus
                cand.update(lst)
        for j, shared in cand.items():
            if j <= i:
                continue
            if shared >= 2 and len(toks[i] & toks[j]) / len(toks[i] | toks[j]) >= threshold:
                parent[find(j)] = find(i)
    # La Ley 30364 reproduce artículos que modifica del CP/CPP (121-A, 122, 242, 377, 378...). Esos chunks y el
    # artículo original no son idénticos (otra versión del texto) pero responden las mismas preguntas: mismo grupo.
    by_article: dict[tuple[str, str], list[str]] = {}
    for i in ids:
        c = corpus[i]
        aid = str((c.get("metadata") or {}).get("article_id") or "").upper().replace(" ", "")
        if aid and c.get("source_type") in ("tipo_02_codigo_penal", "tipo_03_codigo_procesal_penal"):
            by_article.setdefault(("code", aid), []).append(i)
    for i in ids:
        c = corpus[i]
        aid = str((c.get("metadata") or {}).get("article_id") or "").upper().replace(" ", "")
        m = re.match(r"(\d+)", aid)
        if c.get("source_type") == "tipo_01_ley_30364" and m and int(m.group(1)) >= 48:
            for j in by_article.get(("code", aid), []):
                parent[find(j)] = find(i)          # mismo número de artículo = mismo artículo (otra versión del texto)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return {content_key("|".join(v)): v for v in groups.values()}


def _prompts_sha() -> str:
    h = hashlib.sha256()
    for p in sorted((Path(__file__).parent / "prompts").glob("*.txt")):
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()


def write_freeze(out_dir: Path, chunks_path: Path, params: dict) -> None:
    """Congela el corpus y los prompts con los que se genera el dataset (se verifica en los pasos siguientes)."""
    write_json(out_dir / "freeze.json", {"corpus_path": str(chunks_path), "corpus_sha256": sha256_file(chunks_path),
                                         "prompts_sha256": _prompts_sha(), "params": params})


def check_freeze(out_dir: Path, chunks_path: Path) -> None:
    """Aborta si el corpus o los prompts cambiaron desde el paso 1 (mezclaría tandas generadas con insumos distintos).
    ALLOW_CORPUS_CHANGE=1 lo desactiva; sin freeze.json (directorios antiguos) no comprueba nada."""
    import os
    f = out_dir / "freeze.json"
    if not f.exists() or os.environ.get("ALLOW_CORPUS_CHANGE") == "1":
        return
    fr = read_json(f)
    problems = []
    if sha256_file(chunks_path) != fr["corpus_sha256"]:
        problems.append("el corpus cambió desde el paso 1")
    if _prompts_sha() != fr["prompts_sha256"]:
        problems.append("los prompts cambiaron desde el paso 1")
    if problems:
        raise SystemExit("CONGELADO ROTO: " + "; ".join(problems) + ". Si es intencional, vuelve al paso 1 en un directorio "
                         "nuevo o ejecuta con ALLOW_CORPUS_CHANGE=1 (las respuestas ya generadas quedarían desactualizadas).")


def public_chunk(c: dict) -> dict:
    meta = c.get("metadata") or {}
    return {"chunk_id": c["chunk_id"], "source_type": c.get("source_type"), "doc_id": c.get("doc_id"),
            "title": c.get("title"), "article_id": meta.get("article_id"), "text": c.get("text")}


# ---------------------------------------------------------------- BM25 (sin dependencias)
class BM25:
    def __init__(self, ids: list[str], texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.ids, self.k1, self.b = ids, k1, b
        self.docs = [content_tokens(t) for t in texts]
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.N)
        df = Counter(w for d in self.docs for w in set(d))
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
        self.tfs = [Counter(d) for d in self.docs]

    def rank(self, query: str, k: int) -> list[tuple[str, float]]:
        qt = set(content_tokens(query))
        out = []
        for i, (d, tf) in enumerate(zip(self.docs, self.tfs)):
            s = 0.0
            for w in qt:
                if w in tf:
                    s += self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            if s > 0:
                out.append((self.ids[i], s))
        out.sort(key=lambda x: (-x[1], x[0]))
        return out[:k]
