#!/usr/bin/env python3
"""Build the in-game event entries under 用語/ from the kaodata-re events export (koei-events/1).

One entry per event type (docs/events-format.mkdn「條目名」), one H3 per game, ordered by series
(信長之野望 1983 before 三國志 1985) and then by generation. The per-game part sits in a
<!-- data:event-games --> block, so re-running refreshes it and keeps the hand-written intro.
Pictures: https://img.simagame.me/kaodata/event/<dataset>/<file> (scripts/upload_events.py).

Usage: python3 scripts/build_event_entries.py [--dry-run]
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = Path(os.environ.get("EVENTS_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/events"))
OUT = ROOT / "用語"
URL = "https://img.simagame.me/kaodata/event/{}/{}"
DATE = "2026-11-07T12:00:00.000Z"

# dataset -> (kbd, series tag, game page title, platform note); order is the order on the page
GAMES = {
    "nobu4-pc98": ("信4", "信長之野望", "信長之野望・武將風雲錄", "PC-98 版。只用 8 種數位色，以抖色表現層次，畫面色彩如此是原貌。"),
    "nobu6pk-pc98": ("信6", "信長之野望", "信長之野望・天翔記", "PC-98 威力加強版。"),
    "san4pk-pc98": ("三4", "三國志", "三國志IV", "PC-98 威力加強版。"),
}

# game word -> (entry name, intro)
ENTRIES = {
    "一揆": ("一揆", "一揆原指同心協力，後來指農民、地侍、僧侶等結成同盟、以武力對抗領主或權力者的行動，室町至戰國時代各地頻繁發生。"),
    "一向一揆": ("一向一揆", "一向一揆是淨土真宗（一向宗）門徒發動的一揆，以本願寺為中心，曾控制加賀國近百年，並與織田信長長年交戰。"),
    "疫病": ("疫病", "疫病泛指流行的傳染病。古代醫療有限，疫病流行常造成大量人口死亡，也會削弱軍隊與生產。"),
    "豊作": ("豐收", "豐收指農作物收成良好的年份。前近代的國力以米糧為本，收成好壞直接影響錢糧與民心。"),
    "凶作": ("歉收", "歉收指農作物收成不佳的年份，常由天候不順、旱澇或蟲害造成，嚴重時引發飢荒。"),
    "台風": ("颱風", "颱風是西北太平洋生成的熱帶氣旋，夏秋之際侵襲日本與中國沿海，帶來強風豪雨，毀損農作與房舍。"),
    "地震": ("地震", "日本位於板塊交界，自古地震頻繁。戰國時代也有天正大地震（1586 年）等大地震，造成城池崩毀。"),
    "大雪": ("大雪", "大雪指冬季的豪雪。日本海側的北陸、東北等地冬季積雪深厚，會阻斷交通與軍隊行動。"),
    "日照り": ("乾旱", "乾旱指長期不下雨、水源枯竭，使稻作缺水而歉收。"),
    "長雨": ("長雨", "長雨指連綿多日不停的雨，日照不足又易釀成水災，使農作物生長不良。"),
    "飢饉": ("飢荒", "飢荒指糧食嚴重不足、民眾挨餓的災害，多由歉收、天災或戰亂引起。"),
    "反乱": ("民變", "民變指百姓不堪苛政或災荒而起事反抗官府，漢末的黃巾之亂即為一例。"),
    "蝗災": ("蝗災", "蝗災是蝗蟲大量繁殖、成群遷飛，將所經之處的農作物吃光的災害，中國史書多有記載。"),
    "洪水": ("洪水", "洪水指河川因豪雨或長雨暴漲、氾濫成災，黃河、長江流域自古屢有大水。"),
}


def load() -> dict[str, list[tuple[str, dict]]]:
    """entry name -> [(dataset, row)] in page order."""
    by_entry = {}
    for ds in GAMES:
        path = EXPORT / f"{ds}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                by_entry.setdefault(ENTRIES[r["name"]][0], []).append((ds, r))
    return by_entry


def games_block(rows: list[tuple[str, dict]]) -> str:
    out = []
    for ds, r in rows:
        kbd, _, title, note = GAMES[ds]
        out += [f"### [{title}](/遊戲/{title}) <kbd>{kbd}</kbd>", "",
                f"![{title} {r['name']}]({URL.format(ds, r['file'])})", "",
                f"- 遊戲中的稱呼：{r['name']}"]
        if quotes := re.findall(r"「([^」]+)」", r.get("notes", "")):
            out.append("- 遊戲訊息：" + "、".join(f"「{q.replace('%s', '○○')}」" for q in quotes))
        out += [f"- {note}", ""]
    return "\n".join(out).rstrip()


def render(name: str, intro: str, rows: list[tuple[str, dict]]) -> str:
    tags = ", ".join(["事件"] + list(dict.fromkeys(GAMES[ds][1] for ds, _ in rows)))
    return f"""---
title: {name}
description: "{intro.split('。')[0]}。"
published: true
date: {DATE}
tags: {tags}
editor: markdown
dateCreated: {DATE}
---

## 簡介

{intro}

## 遊戲中的事件

<!-- data:event-games begin -->
{games_block(rows)}
<!-- data:event-games end -->
"""


def main() -> None:
    intros = {e: i for e, i in ENTRIES.values()}
    for name, rows in load().items():
        path = OUT / f"{name}.md"
        if path.exists():
            old = path.read_text(encoding="utf-8")
            text = re.sub(r"<!-- data:event-games begin -->\n.*?\n<!-- data:event-games end -->",
                          lambda _: f"<!-- data:event-games begin -->\n{games_block(rows)}\n<!-- data:event-games end -->",
                          old, flags=re.S)
        else:
            text = render(name, intros[name], rows)
        print(f"{name}: {len(rows)} games" + (" (dry run)" if "--dry-run" in sys.argv else ""))
        if "--dry-run" not in sys.argv:
            path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
