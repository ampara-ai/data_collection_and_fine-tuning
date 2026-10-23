#!/usr/bin/env python
"""Paso 1: partición del corpus POR CHUNK (train / dev / test), decidida antes de generar nada.

Por qué por chunk y no por sentencia: un split por sentencia deja los mismos artículos en entrenamiento y evaluación
(los 37 positivos del test oficial ya estaban en el entrenamiento). Aquí los chunks de dev/test no aparecen en el
entrenamiento NI como positivo NI como negativo.

* Chunks con texto idéntico o casi idéntico (Jaccard >= 0.85; p. ej. un artículo repetido en dos tipos de fuente)
  van siempre al mismo lado.
* La asignación es determinista y estable: depende solo de (semilla, texto del chunk), no del orden ni del tamaño del
  corpus. Si mañana se regenera el corpus (nuevo CPP), los chunks que ya existían conservan su partición.
* Chunks demasiado cortos o largos se excluyen (probables errores de parseo); no sirven ni como positivo ni negativo.

Uso: python 01_split_chunks.py [--chunks ...] [--out-dir ...] [--seed 520]
"""
import argparse
from collections import Counter, defaultdict

import config
from common import read_json, load_corpus, near_duplicate_groups, source_code, stable_unit, write_freeze, write_json

ap = argparse.ArgumentParser()
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--seed", type=int, default=config.SEED)
ap.add_argument("--test-frac", type=float, default=config.TEST_FRAC)
ap.add_argument("--dev-frac", type=float, default=config.DEV_FRAC)
ap.add_argument("--extend", action="store_true",
                help="el corpus creció: conserva las particiones ya asignadas y asigna solo los chunks nuevos (los duplicados heredan la de su gemelo)")
args = ap.parse_args()

from pathlib import Path
out_dir = Path(args.out_dir)
corpus = load_corpus(Path(args.chunks))
groups = near_duplicate_groups(corpus)

assignments, excluded = {}, {}
prev = read_json(out_dir / "chunk_split.json")["assignments"] if args.extend and (out_dir / "chunk_split.json").exists() else {}
old_freeze = read_json(out_dir / "freeze.json") if args.extend and (out_dir / "freeze.json").exists() else None
conflicts = 0
for key, ids in groups.items():
    lens = [len(corpus[i].get("text") or "") for i in ids]
    if min(lens) < config.MIN_CHARS:
        reason = f"texto corto (<{config.MIN_CHARS} caracteres)"
    elif max(lens) > config.MAX_CHARS:
        reason = f"texto largo (>{config.MAX_CHARS} caracteres): revisar el parser"
    else:
        reason = None
    if reason:
        for i in ids:
            excluded[i] = reason
        continue
    u = stable_unit(args.seed, key)
    types = {source_code(corpus[i]) for i in ids}
    if types <= {"05"}:                       # 4 chunks institucionales: demasiado pocos para repartir
        split = "train"
    elif any(i in prev for i in ids):                 # corpus extendido: se respeta lo ya asignado
        known = Counter(prev[i] for i in ids if i in prev)
        split = known.most_common(1)[0][0]
        conflicts += int(len(known) > 1)
    elif u < args.test_frac:
        split = "test"
    elif u < args.test_frac + args.dev_frac:
        split = "dev"
    else:
        split = "train"
    for i in ids:
        assignments[i] = split

stats = defaultdict(Counter)
for cid, s in assignments.items():
    stats[source_code(corpus[cid])][s] += 1
for cid in excluded:
    stats[source_code(corpus[cid])]["excluido"] += 1

print(f"chunks: {len(corpus)} | grupos (duplicados agrupados): {len(groups)} | asignados: {len(assignments)} | excluidos: {len(excluded)}")
print(f"{'tipo':6}{'train':>7}{'dev':>6}{'test':>6}{'excl.':>7}   % test")
for t in sorted(stats):
    c = stats[t]; n = c["train"] + c["dev"] + c["test"]
    pct = c["test"] / n if n else 0
    flag = "  <-- desviado" if n >= 30 and abs(pct - args.test_frac) > 0.08 else ""
    print(f"{t:6}{c['train']:>7}{c['dev']:>6}{c['test']:>6}{c['excluido']:>7}   {pct:.0%}{flag}")
for r, n in Counter(excluded.values()).items():
    print(f"excluidos por: {r}: {n}")
for cid, r in excluded.items():
    if "largo" in r:
        print(f"   largo: {cid} ({len(corpus[cid]['text'])} caracteres)")

write_json(out_dir / "chunk_split.json", {
    "params": {"seed": args.seed, "test_frac": args.test_frac, "dev_frac": args.dev_frac,
               "min_chars": config.MIN_CHARS, "max_chars": config.MAX_CHARS},
    "counts": {"train": sum(v == "train" for v in assignments.values()), "dev": sum(v == "dev" for v in assignments.values()),
               "test": sum(v == "test" for v in assignments.values()), "excluded": len(excluded)},
    "assignments": dict(sorted(assignments.items())),
    "duplicate_groups": [v for v in groups.values() if len(v) > 1],
    "excluded": dict(sorted(excluded.items())),
})
if args.extend:
    print(f"[extend] chunks nuevos asignados: {sum(1 for c in assignments if c not in prev)} | grupos con gemelos en particiones distintas: {conflicts}")
write_freeze(out_dir, Path(args.chunks), {k: getattr(config, k) for k in [
    "SEED", "TEST_FRAC", "DEV_FRAC", "CHUNK_QUESTIONS", "MAX_LEXICAL_OVERLAP", "N_NEG_SELECT", "N_NEG_FINAL", "NEG_MIN_RANK",
    "NEG_MAX_SCORE_RATIO", "MAX_NEG_USES", "NEG_JUDGE_FRACTION", "MAX_ROWS_PER_POSITIVE", "PROMPT_VERSION"]})
if old_freeze:   # registro de la extensión deliberada del corpus
    fz = read_json(out_dir / "freeze.json")
    fz["extended_from"] = {"corpus_sha256": old_freeze["corpus_sha256"], "prompts_sha256": old_freeze["prompts_sha256"]}
    write_json(out_dir / "freeze.json", fz)
print("->", out_dir / "chunk_split.json", "(+ freeze.json: corpus y prompts congelados)")
