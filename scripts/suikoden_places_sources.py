#!/usr/bin/env python3
"""Collect the sources for each Suikoden 州 entry, for the intro batch (sanguo_places_batch.py --set suikoden).

Per 州: the game data (writing, Japanese writing, cities, neighbours) and zh.wikipedia intros of the
likely article titles (X, X府, X州). Writes ~/.cache/koei-wiki/suikoden-place-sources.jsonl (not in git;
Wikipedia caches are shared with sanguo_places_sources.py).

Usage: python3 scripts/suikoden_places_sources.py
"""

import json

from build_suikoden_places import GAME, entries
from sanguo_places_sources import CACHE, wiki_intros, wiki_search


def titles_for(e: str) -> list[str]:
    return list(dict.fromkeys([e, e + "府"] + ([] if e.endswith("州") else [e + "州"])))


def main() -> None:
    rows = entries()
    by_id = {p["id"]: p for p in rows}
    wiki = wiki_intros([t for p in rows for t in titles_for(p["entry"])])
    missing = [p["entry"] for p in rows if not any(wiki.get(t) for t in titles_for(p["entry"]))]
    found = {e: t for e, t in wiki_search(missing).items() if t and e in missing and e in t}
    wiki = wiki_intros(list(wiki) + list(found.values()))
    out = CACHE / "suikoden-place-sources.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for p in rows:
            e = p["entry"]
            wk = [w for t in titles_for(e) + ([found[e]] if e in found else []) if (w := wiki.get(t))]
            f.write(json.dumps({"entry": e, "kind": "水滸州", "writing": p["name"], "nameJa": p.get("nameJa"),
                                "cities": p["cities"], "adjacent": [by_id[a]["entry"] for a in p["adjacent"]],
                                "notes": p.get("notes", ""), "wikipedia": list({w["title"]: w for w in wk}.values())},
                               ensure_ascii=False) + "\n")
        f.write(json.dumps({"entry": f"遊戲:{GAME}", "kind": "遊戲", "notes": game_notes(rows)}, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {len(rows)} 州 + 1 game; no wikipedia for {sum(1 for p in rows if p['entry'] in missing and p['entry'] not in found)}")


def game_notes(rows: list[dict]) -> str:
    total = sum(p["cities"] for p in rows)
    return (f"水滸傳・天命之誓（1989，PC-88SR 首發，另有 PC-98、DOS 繁中版、FC 版）。地點單位是州，全國 {len(rows)} 州，"
            f"共 {total} 城；遊戲資料裡州以下的城只是戰場圖上的格子，沒有個別資料。每州一張戰場地圖，依季節（春夏秋冬）換圖。"
            "三個版本的 49 州相鄰關係相同；13 延安的城數中文版 4、日文版與 FC 版 5。"
            "州名中文版與日文版寫法不同的有：太原／大原、鳳祥／風翔、窿德／隆徳、穎州／穎（日文版州表不寫「州」字）。")


if __name__ == "__main__":
    main()
