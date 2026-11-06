#!/usr/bin/env python3
"""Verify the kaodata-re places export (Sanguo and Suikoden) against koei-places/1 (docs/places-format.mkdn).

Usage: python3 scripts/verify_sanguo_places.py [dataset ...]   (default: every <dataset>.jsonl)
PLACES_EXPORT overrides the export directory.
"""

import json
import os
import sys
from pathlib import Path

EXPORT = Path(os.environ.get("PLACES_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/places"))
REQUIRED = ("dataset", "id", "name", "level")
ROLES = {"戰場", "攻城", "野戰", "城門戰", "市街戰", "水戰", "關"}
SEASONS = {"春", "夏", "秋", "冬"}


def verify(dataset: str) -> tuple[int, list[str]]:
    rows = [json.loads(line) for line in (EXPORT / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines() if line]
    checks, errors = 0, []

    def check(ok: bool, msg: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(f"{dataset}: {msg}")

    ids = [r.get("id") for r in rows]
    check(len(ids) == len(set(ids)), "duplicate ids")
    by_id = {r["id"]: r for r in rows if "id" in r}
    for r in rows:
        rid = r.get("id")
        for key in REQUIRED:
            check(key in r, f"{rid}: missing {key}")
        check(r.get("dataset") == dataset, f"{rid}: dataset {r.get('dataset')!r}")
        check(isinstance(r.get("level"), str) and r.get("level") != "", f"{rid}: empty level")
        adj = r.get("adjacent", [])
        for a in adj:
            check(a in by_id, f"{rid}: adjacent {a} missing")
            if a in by_id:
                back = rid in by_id[a].get("adjacent", [])
                if not back:  # allowed only when the upstream explains it on both sides (game data itself is one-way)
                    note, other = r.get("notes", ""), by_id[a].get("name")
                    check(str(a) in note or bool(other) and other in note,
                          f"{rid}: adjacent {a} not mutual and not explained in notes")
                    print(f"  {dataset}: one-way adjacency {rid} -> {a}")
        if "parentCity" in r:
            check(r["parentCity"] in by_id, f"{rid}: parentCity {r['parentCity']} missing")
        for m in r.get("battlemaps", []):
            check(m.get("role") in ROLES, f"{rid}: role {m.get('role')!r}")
            if "season" in m:
                check(m["season"] in SEASONS, f"{rid}: season {m['season']!r}")
            check((EXPORT / dataset / m.get("file", "")).is_file(), f"{rid}: file {m.get('file')} missing")
            for s in m.get("sharedWith", []):
                check(s in by_id, f"{rid}: sharedWith {s} missing")
            if "from" in m:
                check(m["from"] in by_id, f"{rid}: from {m['from']} missing")
                if adj:
                    check(m["from"] in adj, f"{rid}: from {m['from']} not adjacent")
        if "cities" in r:
            check(isinstance(r["cities"], int) and r["cities"] > 0, f"{rid}: cities {r['cities']!r}")
        for key in r.get("uncertain", []):
            check(key in r or key == "level", f"{rid}: uncertain names absent field {key}")
    return checks, errors


def main() -> None:
    datasets = sys.argv[1:] or sorted(p.stem for p in EXPORT.glob("*.jsonl"))
    total, failed = 0, []
    for ds in datasets:
        n, errs = verify(ds)
        total += n
        failed += errs
        print(f"{ds}: {n} checked, {len(errs)} mismatched")
    for e in failed[:50]:
        print("  " + e)
    print(f"total: {total} checked, {len(failed)} mismatched")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
