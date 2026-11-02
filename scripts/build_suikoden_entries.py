#!/usr/bin/env python3
"""Build Suikoden person entries (人物/水滸/*.md) from the mapping, game stats and bios.

Data blocks (<!-- data:x begin/end -->, EDITORIAL §10) are always regenerated.
A missing file or a Wiki.js stub ("Your content here") is written whole from the
template layout (assets/person_suikoden_template.mkdn); any other file only gets
its data blocks replaced.

Links in the bio are added at render time (the jsonl stays plain text): every other
Suikoden person and 梁山泊, first occurrence only, longest name first.

Inputs:
  assets/data/suikoden/suikoden-persons-mapping.csv  names, 綽號, 星號, 座次, kaodata IDs
  assets/data/suikoden/suikoden-bios.jsonl           bio, Wikipedia title
  遊戲/水滸傳・天命之誓/人物資料.md                   PC-98 stats by 遊戲ID

Usage: scripts/build_suikoden_entries.py [--all | 名1 名2 ...] [--dry-run] [--force]
  --force  rewrite whole files even if they are no longer stubs (loses hand edits)
"""

import csv
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/suikoden"
OUT_DIR = ROOT / "人物/水滸"
STATS_MD = ROOT / "遊戲/水滸傳・天命之誓/人物資料.md"
IMG = "https://img.simagame.me/kaodata/faces/suikoden-{}/{}.png"
PLATFORMS = [("pc88", "PC-88"), ("pc98", "PC-98"), ("fc", "FC")]  # release order
STAT_COLS = ["年齡", "性別", "身份", "體力", "能耐", "技能", "智慧", "忠義", "仁愛", "勇氣", "舵"]
# Names never auto-linked: not found in the 120-chapter novel, and short enough to
# match inside other words (e.g. 上青).
NO_LINK = {"上青", "李懷"}
EXTRA_LINKS = {"梁山泊": "/事件/梁山泊"}
# Words that contain a person's name but are not that person (EDITORIAL §6: do not split terms).
PROTECTED = ["石寶塔"]


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def load_stats() -> dict[int, dict]:
    rows = {}
    for line in STATS_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 14 and cells[0].isdigit():
            rows[int(cells[0])] = dict(zip(STAT_COLS, cells[3:]))
    return rows


def portraits(name: str, row: dict) -> str:
    cells = [f'<figure class="kw-face">\n<img src="{IMG.format(p, row[p + "_id"])}" '
             f'alt="{name} 水滸傳・天命之誓 {label}" height="120">\n'
             f"<figcaption><kbd>水</kbd> {label}</figcaption>\n</figure>"
             for p, label in PLATFORMS if row[p + "_id"]]
    return block("portraits", '<div class="kw-portraits">\n' + "\n".join(cells) + "\n</div>")


def stats_block(row: dict, stats: dict) -> str:
    gid = int(row["遊戲ID"])
    s = stats[gid]
    head = "| ID | " + " | ".join(STAT_COLS) + " |"
    align = "| :---: | :---: | :---: | :--- |" + " :---: |" * 8
    vals = "| " + " | ".join([str(gid)] + [s[c] for c in STAT_COLS]) + " |"
    return block("stats-pc98", "\n".join([head, align, vals]))


def link_bio(text: str, self_name: str, targets: dict[str, str]) -> str:
    names = sorted([n for n in targets if n != self_name] + PROTECTED, key=len, reverse=True)
    pat = re.compile("|".join(map(re.escape, names)))
    seen = set()

    def sub(m: re.Match) -> str:
        n = m.group(0)
        if n in seen or n in PROTECTED:
            return n
        seen.add(n)
        return f"[{n}]({targets[n]})"

    return pat.sub(sub, text)


def description(row: dict, bio: str) -> str:
    if row["梁山座次"]:
        return f"梁山泊一百單八將第 {row['梁山座次']} 位，{row['星號']}「{row['綽號']}」。"
    first = bio.split("。")[0] if bio else ""
    if first and "一百零八星" not in first and "座次" not in first:
        return first + "。"
    return "《水滸傳》人物。"


def render_new(row: dict, bio: dict, blocks: dict, targets: dict, old: str) -> str:
    name = row["wiki名"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = m.group(1) if (m := re.search(r"^dateCreated: (\S+)", old, re.M)) else now
    text = (bio or {}).get("bio", "").strip()
    tags = ["水滸", "suikoden"]
    if row["天罡地煞"]:
        tags += ["一百零八星", row["天罡地煞"] + "星"]
    out = ["---", f"title: {name}", f'description: "{description(row, text)}"', "published: true",
           f"date: {now}", f"tags: {', '.join(tags)}", "editor: markdown", f"dateCreated: {created}", "---", "",
           "## 基本資料", "", "| 項目 | 內容 |", "| :--- | :--- |", f"| 姓名 | {row['姓名']} |"]
    if row["綽號"]:
        out.append(f"| 綽號 | {row['綽號']} |")
    if row["星號"]:
        out += [f"| 星號 | {row['星號']} |", f"| 梁山座次 | 第 {row['梁山座次']} 位 |"]
    out += ["", "## 人物畫像", "", blocks["portraits"],
            "", "## 遊戲數值", "", "### 水滸傳・天命之誓（PC-98）", "", blocks["stats-pc98"],
            "", "## 列傳", "", link_bio(text, name, targets) if text else "<!-- 列傳待補 -->"]
    wiki = (bio or {}).get("sources", {}).get("wikipedia")
    if wiki:
        url = "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(wiki.replace(" ", "_"))
        out += ["", "## References", "", f"- [{row['姓名']} - 维基百科]({url})"]
    return "\n".join(out) + "\n"


def replace_blocks(text: str, blocks: dict) -> str:
    for key, body in blocks.items():
        pat = re.compile(rf"<!-- data:{key} begin -->.*?<!-- data:{key} end -->", re.S)
        text = pat.sub(lambda _: body, text)
    return text


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    mapping = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "suikoden-persons-mapping.csv", encoding="utf-8"))}
    bios = {(r := json.loads(line))["name"]: r
            for line in open(DATA / "suikoden-bios.jsonl", encoding="utf-8") if line.strip()}
    stats = load_stats()
    targets = {n: f"/人物/水滸/{n}" for n in mapping if n not in NO_LINK} | EXTRA_LINKS
    names = list(mapping) if "--all" in sys.argv else args
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        row = mapping[name]
        blocks = {"portraits": portraits(row["姓名"], row), "stats-pc98": stats_block(row, stats)}
        path = OUT_DIR / f"{name}.md"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if not old or "Your content here" in old or "--force" in sys.argv:
            text = render_new(row, bios.get(name), blocks, targets, old)
            kind = "new"
        else:
            text = replace_blocks(old, blocks)
            kind = "updated" if text != old else "unchanged"
        counts[kind] += 1
        if not dry and text != old:
            path.write_text(text, encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
