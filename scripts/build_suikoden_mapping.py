#!/usr/bin/env python3
"""Build the Suikoden (水滸傳・天命之誓) person mapping CSV.

Sources:
  - 遊戲/水滸傳・天命之誓/人物資料.md (game stats table, column ID)
  - kaodata face indexes: https://img.simagame.me/kaodata/faces/<dataset>/index.json
  - zh.wikipedia「一百單八將」(rendered as zh-hant) for the 108 stars list

Downloads are cached under CACHE_DIR (outside the repo). Delete the cache to refetch.
Standard library only.

Usage: python3 scripts/build_suikoden_mapping.py [--refresh]
"""

import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATS_MD = REPO / "遊戲" / "水滸傳・天命之誓" / "人物資料.md"
OUT_CSV = REPO / "assets" / "data" / "suikoden" / "suikoden-persons-mapping.csv"
CACHE_DIR = Path.home() / ".cache" / "koei-wiki" / "suikoden"

DATASETS = {"pc88": "suikoden-pc88", "pc98": "suikoden-pc98", "fc": "suikoden-fc"}
KAODATA_URL = "https://img.simagame.me/kaodata/faces/{}/index.json"
WIKI_108_URL = (
    "https://zh.wikipedia.org/w/index.php?title="
    + urllib.parse.quote("一百单八将")
    + "&action=render&variant=zh-hant"
)
USER_AGENT = "koei-wiki-mapping/0.1"

# Japanese shinjitai -> traditional characters seen in the game names
# (and a few in the Wikipedia table). 党 is intentionally absent: the
# novel uses the surname 党 (党世英, 党世雄), not 黨.
SHINJITAI = dict(
    zip(
        "万冲単呉嚢国学宝寿広応懐栄楽横欧沢涛温穂竜蒋覚譲賛銭関霊顕黄値髪挿満",
        "萬沖單吳囊國學寶壽廣應懷榮樂橫歐澤濤溫穗龍蔣覺讓贊錢關靈顯黃值髮插滿",
    )
)

# Names wrong in the game itself (all three platforms), checked against the
# 120-chapter text on zh.wikisource (水滸傳 (120回本)). id -> novel name.
NOVEL_FIXES = {
    47: "朱仝",
    56: "褚亨",
    75: "蔡德章",
    117: "家餘慶",
    159: "鄭之瑞",
}

# Extra notes keyed by game id.
EXTRA_NOTES = {
    140: "小說作「姓何，法諱玄通」",
    191: "小說作「姓寇名烕」",
    227: "即梁中書，小說作「諱世傑」",
    209: "通稱武大郎",
    84: "待考：120回本查無「上青」",
    233: "待考：120回本查無「李懷」",
}


def fetch(url: str, path: Path, refresh: bool) -> str:
    if refresh or not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
    return path.read_text(encoding="utf-8")


def normalize(name: str) -> str:
    return "".join(SHINJITAI.get(c, c) for c in name)


def read_stats_md() -> dict[int, str]:
    rows = {}
    for line in STATS_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[int(m.group(1))] = m.group(2)
    return rows


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def read_108(html: str) -> dict[str, dict]:
    parser = TableRows()
    parser.feed(html)
    stars = {}
    for row in parser.rows:
        m = re.match(r"(\d+)", row[0]) if row else None
        if not m or len(row) < 4:
            continue
        rank = int(m.group(1))
        stars[normalize(row[3])] = {
            "rank": rank,
            "star": normalize(row[1]),
            "nickname": normalize(row[2]),
            "group": "天罡" if rank <= 36 else "地煞",
            "rank_note": "座次依版本或排第93位" if "*" in row[0] else "",
        }
    if len(stars) != 108:
        sys.exit(f"expected 108 stars, parsed {len(stars)}")
    return stars


def same_person_guess(a: str, b: str) -> bool:
    """Loose check: equal length and at most one differing character.

    党/黨 is folded first, since the stats table writes the surname 党 as 黨.
    """
    a, b = a.replace("党", "黨"), b.replace("党", "黨")
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


def main() -> None:
    refresh = "--refresh" in sys.argv
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    md = read_stats_md()
    idx = {}
    for key, ds in DATASETS.items():
        text = fetch(KAODATA_URL.format(ds), CACHE_DIR / f"{ds}.json", refresh)
        idx[key] = {e["id"]: e for e in json.loads(text)}
    stars = read_108(fetch(WIKI_108_URL, CACHE_DIR / "wiki-108-hant.html", refresh))

    rows = []
    for gid in sorted(md):
        md_name = md[gid]
        notes = []
        entries = {k: idx[k].get(gid) for k in DATASETS}
        present = {k: e for k, e in entries.items() if e}
        raw_names = {k: e["name"] for k, e in present.items()}
        # Game spelling: prefer kaodata's historical fix, else normalized game name.
        base = next(iter(present.values()), None)
        game_norm = normalize(base["name"]) if base else md_name
        hist = next((e["nameHistorical"] for e in present.values() if e.get("nameHistorical")), None)
        name = NOVEL_FIXES.get(gid) or hist or game_norm

        if len(set(raw_names.values())) > 1:
            notes.append("各平台寫法不同：" + "、".join(f"{k}「{v}」" for k, v in raw_names.items()))
        if game_norm != name:
            notes.append(f"遊戲作「{base['name'] if base else md_name}」")
        if md_name != name:
            notes.append(f"人物資料.md 作「{md_name}」")
        for k, e in present.items():
            if not same_person_guess(normalize(e["name"]), md_name):
                notes.append(f"{k} id {gid} 為「{e['name']}」，與人物資料.md 不符")
        missing = [k for k in DATASETS if not entries[k]]
        if missing:
            notes.append("無頭像資料：" + "、".join(missing))

        star = stars.get(name, {})
        if star.get("rank_note"):
            notes.append(star["rank_note"])
        if gid in EXTRA_NOTES:
            notes.append(EXTRA_NOTES[gid])

        rows.append(
            {
                "wiki名": name,
                "姓名": name,
                "綽號": star.get("nickname", ""),
                "星號": star.get("star", ""),
                "梁山座次": star.get("rank", ""),
                "天罡地煞": star.get("group", ""),
                "遊戲ID": gid,
                "pc88_id": gid if entries["pc88"] else "",
                "pc98_id": gid if entries["pc98"] else "",
                "fc_id": gid if entries["fc"] else "",
                "備註": "；".join(notes),
            }
        )

    # Disambiguate duplicate names as 名稱_遊戲ID (none expected).
    counts = {}
    for r in rows:
        counts[r["wiki名"]] = counts.get(r["wiki名"], 0) + 1
    for r in rows:
        if counts[r["wiki名"]] > 1:
            r["wiki名"] = f"{r['wiki名']}_{r['遊戲ID']}"
            r["備註"] = "；".join(filter(None, [r["備註"], "重名，wiki名待定區分詞"]))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    in_game = {r["姓名"] for r in rows}
    print(f"rows: {len(rows)}")
    print(f"108 stars in game: {sum(n in in_game for n in stars)}/108")
    print("108 stars missing from game:", [n for n in stars if n not in in_game])
    print(f"non-108 persons in game: {sum(not r['星號'] for r in rows)}")
    print("dup names:", [n for n, c in counts.items() if c > 1])
    print("rows with notes:", sum(bool(r["備註"]) for r in rows))
    print(f"wrote {OUT_CSV.relative_to(REPO)}")


if __name__ == "__main__":
    main()
