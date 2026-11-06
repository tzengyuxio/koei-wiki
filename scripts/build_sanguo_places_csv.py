#!/usr/bin/env python3
"""Build the Sanguo place mapping tables from the kaodata-re export (koei-places/1).

Writes:
  assets/data/sanguo/places.csv            one row per exported place: which entry (if any) it belongs to
  assets/data/sanguo/places-provinces.csv  one row per (dataset, in-game 州): which 州 entry it belongs to

Entry names are the in-game names in Traditional Chinese (EDITORIAL §3.3): Japanese shinjitai and
game typos are normalised here; different names stay different entries. Which levels get entries per
game follows §3.3; field battle spots and map labels are taken when they carry a real place name
(developer labels like 鄴９ are not). Typos and near-identical names map to one entry; the csv keeps
the game writing and how it differs (glyph / typo / alias).
A 州 whose name is also a place entry (SAN14's 羌, 南蠻… are both) shares that entry.

Usage: python3 scripts/build_sanguo_places_csv.py
PLACES_EXPORT overrides the export directory.
"""

import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = Path(os.environ.get("PLACES_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/places"))
OUT = ROOT / "assets/data/sanguo"

# Japanese shinjitai -> Traditional Chinese, as they occur in the export
CHARS = str.maketrans({
    "関": "關", "呉": "吳", "戦": "戰", "晋": "晉", "寿": "壽", "県": "縣", "会": "會", "隷": "隸",
    "楽": "樂", "内": "內", "広": "廣", "剣": "劍", "幷": "并", "蛮": "蠻", "済": "濟", "壷": "壺",
    "恒": "恆", "帯": "帶", "徳": "德", "穣": "穰", "麦": "麥", "温": "溫", "予": "豫", "党": "黨",
    "豊": "豐", "歴": "歷", "霊": "靈", "斉": "齊", "発": "發", "沢": "澤", "乗": "乘", "黄": "黃",
    "当": "當", "巣": "巢", "塩": "鹽", "銭": "錢", "双": "雙", "嶲": "巂",
    "": "涿", "": "郿",  # SAN9 gaiji, read by kana (kaodata-re notes/san-maps.md)
})
# game typos (and shinjitai that stand for a different character here) -> the correct name
TYPOS = {
    "下弁": "下辨", "余汗": "餘汗", "濾水": "瀘水", "泪羅": "汨羅", "崋山": "華山",
    "東來": "東萊", "盧陵港": "廬陵港", "末蘆": "末盧", "蒼悟": "蒼梧", "翻陽": "鄱陽", "晥": "皖",
}
# near-identical names, not typos, merged into one entry named after the writing that appears first in
# the series (user decision 2026-11-06). A name with or without 縣 is not a variant: 代 (the commandery)
# and 代縣 are separate entries.
ALIAS_GROUPS = [
    {"長坂", "長坂坡"}, {"博望", "博望坡"}, {"濡須", "濡須口"}, {"涪", "涪城"}, {"合肥", "合淝"},
    {"烏丸", "烏桓"}, {"荊北", "荊州北部"}, {"荊南", "荊州南部"},
]
ALIASES: dict[str, str] = {}  # filled by main() from the order of appearance
NO_ENTRY = {"異民"}  # SAN9's 州 for the foreign peoples: no 州 entry (user decision 2026-11-06)

INCLUDE = {  # dataset -> (levels that get entries, levels that join only an existing entry)
    "san1-pc98": (set(), set()),
    "san2-pc98": (set(), set()),
    "san3-pc98": ({"州", "據點"}, set()),
    "san4pk-pc98": ({"都市"}, set()),
    "san5pk-pc98": ({"都市"}, set()),
    "san6pk-win": ({"都市", "外族"}, {"野戰地點"}),
    "san7pk-win": ({"都市"}, {"戰場"}),
    "san8pk-win": ({"都市"}, set()),
    "san9pk-win": ({"都市", "異民族", "港", "関"}, {"地名"}),
    "san10pk-win": ({"都市", "関"}, {"拠点"}),
    "san11pk-win": ({"都市", "関", "港"}, set()),
    "san12pk-win": ({"都市"}, set()),
    "san13pk-win": (None, set()),  # None: every level
    "san14pk-win": (None, set()),
}


def norm(name: str) -> tuple[str, str]:
    """Return (entry name, how the game writing differs: "" / glyph / typo / alias)."""
    glyph = name.translate(CHARS)
    typos = {k.translate(CHARS): v for k, v in TYPOS.items()}
    if glyph in typos:
        return typos[glyph], "typo"
    if glyph in ALIASES:
        return ALIASES[glyph], "alias"
    return glyph, "glyph" if glyph != name else ""


def main() -> None:
    data = {ds: [json.loads(line) for line in (EXPORT / f"{ds}.jsonl").read_text(encoding="utf-8").splitlines() if line]
            for ds in INCLUDE}
    for group in ALIAS_GROUPS:  # first appearance: dataset order, then id; places before provinces
        seen = [norm(n)[0] for ds, places in data.items()
                for n in [p["name"] for p in places if p["name"]] + [p.get("province") or "" for p in places]
                if n and norm(n)[0] in group]
        for name in group - {seen[0]}:
            ALIASES[name] = seen[0]
    rows, entries = [], set()
    for ds, places in data.items():
        inc, _ = INCLUDE[ds]
        for p in places:
            if p["name"] and (inc is None or p["level"] in inc):
                entries.add(norm(p["name"])[0])
    for ds, places in data.items():
        inc, cand = INCLUDE[ds]
        for p in places:
            name, entry, diff, rule = p["name"], "", "", "excluded"
            if not name:
                rule = "no-name"
            elif inc is None or p["level"] in inc:
                (entry, diff), rule = norm(name), "level"
            elif p["level"] in cand:
                # SAN6 field spots are named "<city><number>" by the developers
                if re.search(r"[0-9０-９]$", name):
                    rule = "dev-label"
                else:  # a real place name: take it (user decision 2026-11-06)
                    entry, diff = norm(name)
                    rule = "name-match" if entry in entries else "real-name"
            rows.append({"dataset": ds, "id": p["id"], "level": p["level"], "game_name": name or "",
                         "entry": entry, "diff": diff, "rule": rule})
    with open(OUT / "places.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["dataset", "id", "level", "game_name", "entry", "diff", "rule"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    prov = {(ds, p["province"]) for ds, places in data.items() for p in places if p.get("province")}
    with open(OUT / "places-provinces.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dataset", "game_name", "entry", "diff"])
        for ds, name in sorted(prov, key=lambda x: (list(INCLUDE).index(x[0]), x[1])):
            entry, diff = ("", "") if name in NO_ENTRY else norm(name)
            w.writerow([ds, name, entry, diff])

    used = {r["entry"] for r in rows if r["entry"]}
    print(f"places.csv: {len(rows)} rows, {len(used)} entries")
    for rule in ("level", "name-match", "real-name", "dev-label", "excluded", "no-name"):
        print(f"  {rule}: {sum(r['rule'] == rule for r in rows)}")
    pe = {norm(n)[0] for _, n in prov if n not in NO_ENTRY}
    print(f"places-provinces.csv: {len(prov)} rows, {len(pe)} 州 entries, {len(pe - used)} not also a place entry")


if __name__ == "__main__":
    main()
