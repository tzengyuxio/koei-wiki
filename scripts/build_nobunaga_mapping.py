#!/usr/bin/env python3
"""Build the Nobunaga person mapping: wiki entry <-> in-game IDs per kaodata-re dataset.

Design: docs/backlog/nobunaga-persons.mkdn.

Inputs
  - kaodata-re export/koei-wiki/persons/<dataset>.jsonl   (koei-persons/1)
  - assets/data/nobunaga/persons-overrides.csv   hand-made fixes: dataset,id,wiki名[,備註]
                                                 (merges renamed people, splits namesakes; wiki名 "-" = do not map)

Matching: the Japanese name (nameJa, else name), converted to the wiki name, is the key; a key is split into several people only
when one dataset has it more than once (see cluster()). The wiki name is the key converted to
Traditional Chinese (OpenCC jp2t + t2tw, plus Taiwan forms in TW_FIX).

Outputs
  - assets/data/nobunaga/persons-mapping.csv     one row per wiki entry, one column per dataset
                                                 (several ids joined by "|" when the game has the person twice)
  - assets/data/nobunaga/persons-unmatched.csv   rows to review: namesakes, missing birth years,
                                                 possible renames (same birth and death year, same given name)

Usage: python3 scripts/build_nobunaga_mapping.py
"""

import csv
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/nobunaga"
EXPORT = Path(os.environ.get("KOEI_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki")) / "persons"
DATASETS = [
    "nobu2-pc88", "nobu3-pc98", "nobu4-pc98", "nobu5pk-win", "nobu6pk-pc98", "nobu7pk-win",
    "nobu8pk-win", "nobu9pk-win", "nobu10pk-win", "nobu11pk-win", "nobu12pk-win", "nobu13pk-win",
]
TW_FIX = str.maketrans({"内": "內", "戸": "戶", "鄕": "鄉", "眞": "真", "衞": "衛", "郞": "郎", "蛎": "蠣",
                        "万": "萬", "鎭": "鎮", "姉": "姊"})
RENAME_BORN_GAP = 2
FIRST_BATCH_GENERATIONS = 8


def to_tw(names: list[str]) -> list[str]:
    """Japanese names -> Traditional Chinese (Taiwan) as used for entry names."""
    text = "\n".join(names)
    for cfg in ("jp2t.json", "t2tw.json"):
        text = subprocess.run(["opencc", "-c", cfg], input=text, capture_output=True, text=True, check=True).stdout
    out = []
    for n in text.rstrip("\n").split("\n"):
        n = n.translate(TW_FIX)
        while "々" in n:  # 佐々成政 -> 佐佐成政
            i = n.index("々")
            n = n[:i] + n[i - 1] + n[i + 1:]
        out.append(n)
    return out


def load() -> list[dict]:
    rows = []
    for ds in DATASETS:
        for line in (EXPORT / f"{ds}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = json.loads(line)
                rows.append({"dataset": ds, "id": p["id"], "ja": p.get("nameJa") or p["name"], "game": p["name"],
                             "born": p.get("born"), "died": p.get("died"),
                             "daimyo": any(s.get("status") == "大名" for s in p.get("scenarios", []))})
    return rows


def cluster(recs: list[dict]) -> list[list[dict]]:
    """Split records sharing one name into people.

    Birth years differ by several years between generations, so one name is one person unless a single
    dataset has it as different people. Records of one dataset born within a year of each other are the
    same person (3 and 4 keep one record per scenario for some people); if a dataset still has several,
    those seed the people and the other datasets join the seed with the nearest birth year.
    """
    units = defaultdict(list)  # dataset -> list of record groups (one group = one person in that game)
    for r in recs:
        for u in units[r["dataset"]]:
            if r["born"] is None or any(x["born"] is None or abs(x["born"] - r["born"]) <= 1 for x in u):
                u.append(r)
                break
        else:
            units[r["dataset"]].append([r])
    most = max(units.values(), key=len)
    if len(most) == 1:
        return [recs]
    people = [list(u) for u in most]
    for ds, groups in units.items():
        if groups is most:
            continue
        for u in groups:
            born = next((x["born"] for x in u if x["born"] is not None), None)
            free = [p for p in people if ds not in {x["dataset"] for x in p}] or people
            if born is not None:
                free.sort(key=lambda p: min((abs(born - x["born"]) for x in p if x["born"] is not None), default=99))
            free[0].extend(u)
    return people


def main() -> None:
    rows = load()
    overrides = {}
    ov_file = DATA / "persons-overrides.csv"
    if ov_file.exists():
        with ov_file.open(encoding="utf-8") as f:
            overrides = {(r["dataset"], int(r["id"])): r["wiki名"] for r in csv.DictReader(f)}

    forced = defaultdict(list)
    by_key = defaultdict(list)
    for r in rows:
        name = overrides.get((r["dataset"], r["id"]))
        if name == "-":
            continue
        (forced[name] if name else by_key[r["ja"]]).append(r)

    keys = sorted(by_key)
    by_tw = defaultdict(list)  # 竜造寺 and 龍造寺 (old and new forms in different games) meet here
    for k, name in zip(keys, to_tw(keys)):
        by_tw[name] += by_key[k]
    entries = defaultdict(list)  # wiki name -> list of people (each a list of records)
    for name, recs in by_tw.items():
        entries[name] += cluster(recs)
    for name, recs in forced.items():  # renamed people join the entry of their main name
        if len(entries[name]) == 1:
            entries[name][0] += recs
        else:
            entries[name].append(recs)

    review = []
    out = []
    for name in sorted(entries):
        people = entries[name]
        for i, recs in enumerate(people):
            wiki = name if len(people) == 1 else f"{name}_{i + 1}"
            if len(people) > 1:
                review.append({"類別": "同名異人", "wiki名": wiki, "說明": f"生年 {sorted({r['born'] for r in recs if r['born']})}"})
            ids = defaultdict(list)
            for r in recs:
                ids[r["dataset"]].append(str(r["id"]))
            borns = sorted(r["born"] for r in recs if r["born"] is not None)
            dieds = sorted(r["died"] for r in recs if r["died"] is not None)
            game = sorted({r["game"] for r in recs} - {name, recs[0]["ja"]})
            out.append({"wiki名": wiki, "日文名": recs[0]["ja"], "遊戲寫法": "、".join(game),
                        "生年": borns[len(borns) // 2] if borns else "", "卒年": dieds[len(dieds) // 2] if dieds else "",
                        "大名": "1" if any(r["daimyo"] for r in recs) else "", "代數": len(ids),
                        "第一批": "1" if any(r["daimyo"] for r in recs) or len(ids) >= FIRST_BATCH_GENERATIONS else "",
                        **{ds: "|".join(sorted(ids[ds], key=int)) if ds in ids else "" for ds in DATASETS}})

    # possible renames: same death year, birth within RENAME_BORN_GAP, no shared dataset, and the same
    # given name (羽柴秀吉／豐臣秀吉) or the same family name (細川藤孝／細川幽齋); last two / first two characters
    groups = defaultdict(list)
    for o in out:
        if o["生年"] and o["卒年"]:
            base = o["wiki名"].split("_")[0]
            groups[(o["卒年"], "名", base[-2:])].append(o)
            groups[(o["卒年"], "姓", base[:2])].append(o)
    found = set()
    for g in groups.values():
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                if abs(a["生年"] - b["生年"]) > RENAME_BORN_GAP:
                    continue
                if any(a[ds] != "" and b[ds] != "" for ds in DATASETS) or (a["wiki名"], b["wiki名"]) in found:
                    continue
                found.add((a["wiki名"], b["wiki名"]))
                review.append({"類別": "可能改名", "wiki名": f"{a['wiki名']}、{b['wiki名']}",
                               "說明": f"{a['生年']}–{a['卒年']}／{b['生年']}–{b['卒年']}"})

    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "persons-mapping.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    with (DATA / "persons-unmatched.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["類別", "wiki名", "說明"])
        w.writeheader()
        w.writerows(review)

    used = sum(len(o[ds].split("|")) for o in out for ds in DATASETS if o[ds] != "")
    print(f"{len(rows)} records -> {len(out)} entries ({used} mapped), "
          f"first batch {sum(1 for o in out if o['第一批'])}, review {len(review)}")


if __name__ == "__main__":
    main()
