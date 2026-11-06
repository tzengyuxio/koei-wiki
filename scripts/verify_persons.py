#!/usr/bin/env python3
"""Verify the kaodata-re persons export against koei-persons/1 (docs/persons-format.mkdn).

Checks every row of persons/<dataset>.jsonl: required fields, dataset name, unique ids, field types,
person ids referenced by relations and scenarios[].lord, scenarios[].location against the places export of
the same dataset, and that each biography (<export>/<dataset>.jsonl) belongs to a person. Keys outside the
format are listed as warnings, not counted as mismatches.

Usage: python3 scripts/verify_persons.py [dataset ...]   (default: every persons/<dataset>.jsonl)
KOEI_EXPORT overrides the export directory (kaodata-re export/koei-wiki).
"""

import json
import os
import sys
from pathlib import Path

EXPORT = Path(os.environ.get("KOEI_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki"))
TOP = {"dataset", "id", "name", "nameJa", "courtesy", "reading", "born", "died", "debut", "stats", "more", "hidden",
       "aptitude", "skills", "relations", "scenarios", "game", "uncertain", "notes"}
OBJECTS = ("stats", "more", "hidden", "aptitude", "skills", "relations", "game")
INTS = ("born", "died", "debut")
SCENARIO = {"scenario", "year", "lord", "location", "status", "loyalty", "debut", "rank"}
NOT_YET = {"未登場", "後登場"}  # scenarios where the person appears later; debut is required
RELATIONS = {"father", "mother", "children", "siblings", "spouse", "sworn", "clan"}


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(dataset: str) -> tuple[int, list[str], set[str]]:
    rows = load(EXPORT / "persons" / f"{dataset}.jsonl")
    places_file = EXPORT / "places" / f"{dataset}.jsonl"
    places = {p["id"] for p in load(places_file)} if places_file.exists() else None
    checks, errors, extra = 0, [], set()

    def check(ok: bool, msg: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(f"{dataset}: {msg}")

    ids = [r.get("id") for r in rows]
    check(len(ids) == len(set(ids)), "duplicate ids")
    persons = set(ids)
    for r in rows:
        rid = r.get("id")
        check(r.get("dataset") == dataset, f"{rid}: dataset {r.get('dataset')!r}")
        check(isinstance(rid, int), f"{rid}: id is not int")
        check(isinstance(r.get("name"), str) and r["name"] != "", f"{rid}: empty name")
        extra |= {k for k in r if k not in TOP}
        for k in OBJECTS:
            if k in r:
                check(isinstance(r[k], dict), f"{rid}: {k} is not an object")
        for k in INTS:
            if k in r:
                check(isinstance(r[k], int), f"{rid}: {k} is not int")
        if "nameJa" in r:
            check(r["nameJa"] != r.get("name"), f"{rid}: nameJa equals name")
        for k, v in r.get("relations", {}).items():
            if k not in RELATIONS:
                extra.add(f"relations.{k}")
            elif k == "clan":
                check(isinstance(v, int), f"{rid}: relations.clan is not int")
            else:
                for p in v:
                    check(p in persons, f"{rid}: relations.{k} {p} missing")
        for s in r.get("scenarios", []):
            extra |= {f"scenarios[].{k}" for k in s if k not in SCENARIO}
            check("scenario" in s, f"{rid}: scenario without scenario key")
            if s.get("status") in NOT_YET:
                check(isinstance(s.get("debut"), int), f"{rid}: scenario {s.get('scenario')} {s['status']} without debut")
            if "lord" in s:
                check(s["lord"] in persons, f"{rid}: scenario {s.get('scenario')} lord {s['lord']} missing")
            if "location" in s and places is not None:
                check(s["location"] in places, f"{rid}: scenario {s.get('scenario')} location {s['location']} missing")
    bios = EXPORT / f"{dataset}.jsonl"
    if bios.exists():
        for b in load(bios):
            check(b.get("id") in persons, f"biography {b.get('id')} {b.get('name')} has no person")
    return checks, errors, extra


def main() -> None:
    datasets = sys.argv[1:] or sorted(p.stem for p in (EXPORT / "persons").glob("*.jsonl"))
    total, failed = 0, []
    for ds in datasets:
        checks, errors, extra = verify(ds)
        total += checks
        failed += errors
        print(f"{ds}: {checks} checks, {len(errors)} mismatched" + (f"; keys outside the format: {', '.join(sorted(extra))}" if extra else ""))
    for e in failed[:50]:
        print("  " + e)
    print(f"total: {total} checks, {len(failed)} mismatched")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
