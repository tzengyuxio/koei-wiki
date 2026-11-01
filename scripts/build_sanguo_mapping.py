#!/usr/bin/env python3
"""Build the Sanguo person mapping: wiki entry <-> in-game IDs per kaodata dataset.

Inputs
  - 人物/三國/*.md                         wiki entries (file stem = wiki name)
  - assets/data/sanguo/sanguo-bios.jsonl   faction per wiki name
  - kaodata index.json per dataset         https://img.simagame.me/kaodata/faces/<dataset>/index.json
  - assets/data/sanguo/persons-overrides.csv   hand-made fixes: dataset,id,wiki名[,備註]
                                           (wiki名 "-" means: not a Sanguo person, do not map)
  - assets/data/sanguo/persons-new.csv         Sanguo people without a wiki file yet: wiki名,勢力,出典,備註
  - assets/data/sanguo/persons-excluded.csv    characters deliberately not mapped: dataset,id,類別,備註

Outputs
  - assets/data/sanguo/persons-mapping.csv     one row per wiki entry, one column per dataset
  - assets/data/sanguo/persons-unmatched.csv   game characters left unmapped, for review

Usage: scripts/build_sanguo_mapping.py [--refresh]
"""

import csv
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/sanguo"
CACHE = Path.home() / ".cache/koei-wiki/kaodata-faces"
BASE_URL = "https://img.simagame.me/kaodata/faces"

MAINLINE = [
    "san1-pc98", "san2-pc98", "san3-pc98", "san4pk-pc98", "san5pk-pc98",
    "san6pk-win", "san7pk-win", "san8pk-win", "san9pk-win", "san10pk-win",
    "san11pk-win", "san12pk-win", "san13pk-win", "san14pk-win",
]
OTHERS = ["san1-fc", "san2-fc", "san1-sfc", "san2-sfc", "san1-x68", "eiketsu-pc98"]
DATASETS = MAINLINE + OTHERS

# Japanese shinjitai -> traditional, limited to characters seen in names.
SHINJITAI = str.maketrans(
    "関挙彜歩国随厨楽豊温勲蒋鉄将蛮覧沢姫竜栄広応観権寿斉済霊帰辺郷単献恵顕総継続静争円伝与予"
    "黒歳発険剣戦満禅闘徳撃当党会処実粛囲図団学覚拠旧巌弥従径悪担拝来歓気渉渓焼独産県礼称穏粋"
    "経聡聴舎芸薬虚衆装覇読譲賛転軽辞遅釈銭録陥隠雑頼顔駆験鶏麦黄斎亀仏変数様楼滝砕"
    "煕懐呉厳横繍隲双触黙麹羣児宝寛叙讃齢彦帯朶倹万戯区兪悦壱蝉増乱",
    "關舉彝步國隨廚樂豐溫勳蔣鐵將蠻覽澤姬龍榮廣應觀權壽齊濟靈歸邊鄉單獻惠顯總繼續靜爭圓傳與豫"
    "黑歲發險劍戰滿禪鬪德擊當黨會處實肅圍圖團學覺據舊巖彌從徑惡擔拜來歡氣涉溪燒獨產縣禮稱穩粹"
    "經聰聽舍藝藥虛眾裝霸讀讓贊轉輕辭遲釋錢錄陷隱雜賴顏驅驗雞麥黃齋龜佛變數樣樓瀧碎"
    "熙懷吳嚴橫繡騭雙觸默麴群兒寶寬敘讚齡彥帶朵儉萬戲區俞悅壹蟬增亂",
)
# Variant characters folded only for comparison (both sides), never written out.
FOLD = str.maketrans("脩毗儁雋橋彊毌彤冑鐘祿寗鞠", "修毘雋雋喬疆毋肜胄鍾禄甯麴")

# Whole-name aliases: game spelling (after SHINJITAI) -> wiki base name.
ALIASES = {
    "許子將": "許劭",
    "梁剛": "梁綱",
    "傅儉": "傅僉",
    "尚寵": "向寵",
    "張咨": "張資",
    "劉畯": "劉晙",
    "田與": "田豫",
    "祝融夫人": "祝融",
    "龐義": "龐羲",
    "董荼奴": "董荼那",
    "太史亨": "太史享",
}


def fold(name: str) -> str:
    name = name.translate(SHINJITAI)
    name = ALIASES.get(name, name)
    return name.translate(FOLD)


def load_index(dataset: str, refresh: bool) -> list[dict]:
    path = CACHE / f"{dataset}.json"
    if refresh or not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        # Cloudflare rejects urllib's default User-Agent with 403.
        req = urllib.request.Request(
            f"{BASE_URL}/{dataset}/index.json", headers={"User-Agent": "koei-wiki-mapping/1"}
        )
        with urllib.request.urlopen(req) as r:
            path.write_bytes(r.read())
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_wiki() -> tuple[list[str], dict[str, str]]:
    names = {p.stem for p in (ROOT / "人物/三國").glob("*.md") if p.stem != "home"}
    faction = {}
    with open(DATA / "sanguo-bios.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            faction[row["name"]] = row.get("faction", "")
    for row in read_csv("persons-new.csv"):
        names.add(row["wiki名"])
        faction.setdefault(row["wiki名"], row.get("勢力", ""))
    return sorted(names), faction


def load_overrides() -> dict[tuple[str, int], str]:
    overrides = {(r["dataset"], int(r["id"])): r["wiki名"] for r in read_csv("persons-overrides.csv")}
    for r in read_csv("persons-excluded.csv"):
        overrides.setdefault((r["dataset"], int(r["id"])), "-")
    return overrides


def main() -> None:
    refresh = "--refresh" in sys.argv
    wiki, faction = load_wiki()
    overrides = load_overrides()

    by_key = defaultdict(list)  # folded base name -> wiki names
    for w in wiki:
        by_key[fold(w.split("_")[0])].append(w)

    mapping = {w: defaultdict(list) for w in wiki}
    unmatched = []
    for ds in DATASETS:
        for ch in load_index(ds, refresh):
            cid = ch["id"]
            shown = ch.get("nameHistorical") or ch.get("nameZh") or ch["name"]
            target = overrides.get((ds, cid))
            if target == "-":
                continue
            if target is None:
                candidates = by_key.get(fold(shown), [])
                if len(candidates) == 1:
                    target = candidates[0]
                else:
                    reason = "ambiguous" if candidates else "no-entry"
                    unmatched.append([ds, cid, ch["name"], shown, reason, "|".join(candidates)])
                    continue
            if target not in mapping:
                unmatched.append([ds, cid, ch["name"], shown, "override-unknown-entry", target])
                continue
            mapping[target][ds].append(str(cid))

    with open(DATA / "persons-mapping.csv", "w", encoding="utf-8", newline="") as f:
        out = csv.writer(f)
        out.writerow(["wiki名", "勢力", *DATASETS])
        for w in wiki:
            out.writerow([w, faction.get(w, ""), *("|".join(mapping[w][ds]) for ds in DATASETS)])

    with open(DATA / "persons-unmatched.csv", "w", encoding="utf-8", newline="") as f:
        out = csv.writer(f)
        out.writerow(["dataset", "id", "name", "顯示名", "原因", "候選"])
        out.writerows(unmatched)

    multi = sum(1 for w in wiki for ds in DATASETS if len(mapping[w][ds]) > 1)
    absent = [w for w in wiki if not any(mapping[w][ds] for ds in MAINLINE)]
    reasons = defaultdict(int)
    for row in unmatched:
        reasons[row[4]] += 1
    print(f"wiki entries: {len(wiki)}")
    print(f"entries in no mainline game: {len(absent)} {absent[:20]}")
    print(f"cells with multiple ids: {multi}")
    print(f"unmatched characters: {len(unmatched)} {dict(reasons)}")


if __name__ == "__main__":
    main()
