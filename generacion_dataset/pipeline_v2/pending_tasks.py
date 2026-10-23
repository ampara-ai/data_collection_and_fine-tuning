#!/usr/bin/env python
"""Lista las tareas pendientes de un paso (peticiones sin respuesta), para repartirlas entre agentes o sesiones.

  python pending_tasks.py --out-dir DIR --step 05_judge [--limit 20] [--shard 2/5]

--shard K/N reparte las tareas pendientes entre N agentes (el agente K toma las de índice ≡ K-1 mod N), de modo que
varios agentes (Claude Code, Codex, ...) puedan trabajar en paralelo sin pisarse. Imprime una ruta por línea.
"""
import argparse
from pathlib import Path

import config

ap = argparse.ArgumentParser()
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--step", required=True, help="02_case_questions | 03_chunk_questions | 05_judge | 07_pool_dev | 07_pool_test")
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--shard", default=None, help="K/N")
args = ap.parse_args()

base = Path(args.out_dir).resolve() / "work" / args.step
done = {p.name for p in (base / "responses").glob("*.json")} if (base / "responses").exists() else set()
reqs = sorted(p for p in (base / "requests").glob("*.json") if p.name not in done)
if args.shard:
    k, n = (int(x) for x in args.shard.split("/"))
    reqs = [p for i, p in enumerate(reqs) if i % n == k - 1]
for p in reqs[: args.limit]:
    print(p)
