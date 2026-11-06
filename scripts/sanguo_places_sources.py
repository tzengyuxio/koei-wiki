#!/usr/bin/env python3
"""Collect the sources for each Sanguo place / 州 entry, for the intro batch (sanguo_places_batch.py).

Per entry: how the games use the name (levels, owner, game writings), the hanjunzhi units bearing the
name in 140 CE (the 續漢書郡國志 baseline) with their commandery and 州, and zh.wikipedia intros of the
likely article titles. Writes ~/.cache/koei-wiki/place-sources.jsonl (not in git; Wikipedia is fetched
once and cached in ~/.cache/koei-wiki/wiki-intros.json).

Usage: python3 scripts/sanguo_places_sources.py
"""

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/sanguo"
EXPORT = Path.home() / "works/kaodata-re/export/koei-wiki/places"
HANJUNZHI = Path.home() / "works/hanjunzhi/src/generated/data.json"  # built by `npm run data` there
CACHE = Path.home() / ".cache/koei-wiki"
YEAR = 140  # 永和五年, the 續漢書郡國志 baseline (EDITORIAL §3.3)
TYPES = {"xian": "縣", "houguo": "侯國", "jun": "郡", "guo": "王國", "zhou": "州", "shuguo": "屬國", "yi": "邑", "gongguo": "公國"}
UA = "koei-wiki-places/0.1 (https://koei.wiki; batch source collection)"


def year_of(b, default):
    return default if b is None else b.get("year", b.get("before", b.get("after", default)))


def phase_at(unit, y=YEAR):
    for p in unit["phases"]:
        if year_of(p.get("start"), -9999) <= y < year_of(p.get("end"), 9999):
            return p
    return None


def hanjunzhi_index():
    units = {u["id"]: u for u in json.loads(HANJUNZHI.read_text(encoding="utf-8"))["units"]}
    idx = defaultdict(list)
    for u in units.values():
        p = phase_at(u)
        if not p:
            continue
        chain, par = [], p.get("parent")
        while par and par in units and (pp := phase_at(units[par])):
            chain.append(pp["name"])
            par = pp.get("parent")
        idx[p["name"]].append({"name": p["name"], "type": TYPES.get(p["type"], p["type"]), "within": chain,
                               "seat": p.get("seat"), "note": (p.get("note") or "")[:200]})
    return idx


def wiki_intros(titles: list[str]) -> dict[str, dict]:
    cache_file = CACHE / "wiki-intros.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    todo = [t for t in dict.fromkeys(titles) if t not in cache]
    for i in range(0, len(todo), 20):  # extracts: at most 20 intros per request
        chunk = todo[i:i + 20]
        q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "extracts|pageprops", "explaintext": 1,
                                    "exintro": 1, "redirects": 1, "variant": "zh-tw", "titles": "|".join(chunk)})
        req = urllib.request.Request(f"https://zh.wikipedia.org/w/api.php?{q}", headers={"User-Agent": UA})
        d = json.load(urllib.request.urlopen(req, timeout=60))["query"]
        alias = {r["from"]: r["to"] for r in d.get("normalized", []) + d.get("redirects", [])}
        pages = {p["title"]: p for p in d["pages"].values()}
        for t in chunk:
            final = t
            while final in alias:
                final = alias[final]
            p = pages.get(final, {})
            ok = "missing" not in p and "disambiguation" not in p.get("pageprops", {}) and p.get("extract")
            cache[t] = {"title": final, "extract": p["extract"][:1500]} if ok else {}
        time.sleep(1)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def wiki_search(names: list[str]) -> dict[str, str]:
    """Top zh.wikipedia search hit per name (for titles the direct lookup misses, e.g. no traditional redirect)."""
    cache_file = CACHE / "wiki-search.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    for n in [n for n in names if n not in cache]:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "list": "search", "srlimit": 1,
                                    "srsearch": f"{n} 三國", "variant": "zh-tw"})
        req = urllib.request.Request(f"https://zh.wikipedia.org/w/api.php?{q}", headers={"User-Agent": UA})
        hits = json.load(urllib.request.urlopen(req, timeout=60))["query"]["search"]
        cache[n] = hits[0]["title"] if hits else ""
        time.sleep(0.5)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def titles_for(e: str) -> list[str]:
    base = e[:-1] if e[-1] in "港沖" and len(e) > 2 else e
    out = [e, base + "縣", base + "郡", base + "國", base + "州"] if len(base) <= 2 else [e]
    return list(dict.fromkeys(out + [base]))


def main() -> None:
    rows = list(csv.DictReader((DATA / "places.csv").open(encoding="utf-8")))
    provs = list(csv.DictReader((DATA / "places-provinces.csv").open(encoding="utf-8")))
    export = {}
    for f in EXPORT.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            export[(p["dataset"], p["id"])] = p
    games = defaultdict(list)
    for r in rows:
        if r["entry"]:
            p = export[(r["dataset"], int(r["id"]))]
            games[r["entry"]].append({"dataset": r["dataset"], "level": r["level"], "writing": r["game_name"],
                                      "province": p.get("province")})
    place_entries = set(games)
    members = defaultdict(list)  # (dataset, in-game 州) -> member place names
    for p in export.values():
        if p.get("province") and p.get("name"):
            members[(p["dataset"], p["province"])].append(p["name"])
    peoples = {"倭", "氐", "羌", "南蠻", "山越", "烏丸", "鮮卑", "匈奴"}  # their 州 shares the place entry
    kinds = {}
    for r in provs:
        if not r["entry"] or r["entry"] in place_entries and r["entry"] in peoples:
            continue
        key = f"州:{r['entry']}" if r["entry"] in place_entries else r["entry"]  # 徐州: the 州 apart from the city
        kinds[key] = "州"
        games[key].append({"dataset": r["dataset"], "level": "州", "writing": r["game_name"],
                           "members": members[(r["dataset"], r["game_name"])]})
    idx = hanjunzhi_index()
    wiki = wiki_intros([t for e in games for t in titles_for(e)])
    missing = [e for e in games if not any(wiki.get(t) for t in titles_for(e))]
    # keep a search hit only if its title shares the name's leading characters (drops hits like 「三国」)
    found = {e: t for e, t in wiki_search(missing).items() if t and e in games and e[:2][0] in t and e[:2][-1] in t}
    wiki = wiki_intros(list(wiki) + list(found.values()))
    out = CACHE / "place-sources.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for key, g in sorted(games.items()):
            e = key.removeprefix("州:")
            base = e[:-1] if e[-1] in "港沖" and len(e) > 2 else e
            han = [u for k in dict.fromkeys([e, base, base + "郡", base + "國"]) for u in idx.get(k, [])]
            if e.endswith("縣"):
                han += idx.get(e[:-1], [])
            wk = [w for t in titles_for(e) + ([found[e]] if e in found else []) if (w := wiki.get(t))]
            wk = list({w["title"]: w for w in wk}.values())
            f.write(json.dumps({"entry": key, "kind": kinds.get(key, "地點"), "games": g, "hanjunzhi": han, "wikipedia": wk},
                               ensure_ascii=False) + "\n")
        for label, title, places in game_sections():
            f.write(json.dumps({"entry": f"遊戲:{title}", "kind": "遊戲", "notes": label and places}, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {len(games)} entries + 14 games")


NOTES = Path.home() / "works/kaodata-re/notes/san-maps.md"
LABELS = [("I", "三國志"), ("II", "三國志II"), ("III", "三國志III"), ("IV", "三國志IV"), ("V", "三國志V"),
          ("VI", "三國志VI"), ("VII", "三國志VII"), ("VIII", "三國志VIII"), ("IX", "三國志IX"), ("X", "三國志X"),
          ("11", "三國志11"), ("12", "三國志12"), ("13", "三國志13"), ("14", "三國志14")]


def game_sections():
    """kaodata-re's notes on each game's places (without the long tables), for the city-list 概要."""
    lines = NOTES.read_text(encoding="utf-8").splitlines()
    for label, title in LABELS:
        start = next(i for i, l in enumerate(lines) if re.match(rf"#{{2,3}} {label}（", l))
        depth = len(lines[start].split(" ")[0])
        end = next((i for i in range(start + 1, len(lines)) if re.match(rf"#{{2,{depth}}} ", lines[i])), len(lines))
        body = [l for l in lines[start:end] if not l.startswith("|")]
        yield label, title, "\n".join(body)[:4000]


if __name__ == "__main__":
    main()
