#!/usr/bin/env python3
"""Build the L'Empereur person index 人物/拿破崙時代.md from the entries themselves.

Reads each entry's title, 國籍, 中文譯名 and 原文 from its 基本資料 table and the game ID
from its 遊戲數值 table, then writes the data:index block: one table per country
(largest first, by game ID), plus the event-only characters that have no game ID.
A missing file or an empty page gets a header; otherwise only the block is replaced.

Usage: scripts/build_lempe_person_index.py [--dry-run]
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "人物/拿破崙時代"
INDEX = ROOT / "人物/拿破崙時代.md"  # beside the folder, so the breadcrumb link resolves


def field(text: str, name: str) -> str:
    m = re.search(rf"^\| {name} \| (.*?) \|", text, re.M)
    return m.group(1).strip() if m else ""


def load() -> list[dict]:
    people = []
    for f in sorted(DIR.glob("*.md")):
        t = f.read_text(encoding="utf-8")
        gid = re.search(r"^\| (\d+) \|", t, re.M)
        people.append({
            "path": f"/人物/拿破崙時代/{f.stem}",
            "title": re.search(r"^title: (.*)", t, re.M).group(1).strip(),
            "country": field(t, "國籍"),
            "zh": field(t, "中文譯名"),
            "orig": field(t, "原文"),
            "id": int(gid.group(1)) if gid else None,
        })
    return people


def index_block(people: list[dict]) -> str:
    def row(p: dict) -> str:
        return f"| {'' if p['id'] is None else p['id']} | [{p['title']}]({p['path']}) | {p['zh']} | {p['orig']} |"

    head = ["| ID | 遊戲中名稱 | 中文譯名 | 原文 |", "| ---: | :--- | :--- | :--- |"]
    by_country: dict[str, list] = {}
    for p in people:
        if p["id"] is not None:
            by_country.setdefault(p["country"], []).append(p)
    out = []
    for country, members in sorted(by_country.items(), key=lambda kv: -len(kv[1])):
        out += [f"## [{country}](/用語/{country})（{len(members)} 人）", "", *head]
        out += [row(p) for p in sorted(members, key=lambda p: p["id"])]
        out.append("")
    events = [p for p in people if p["id"] is None]
    if events:
        out += [f"## 事件角色（{len(events)} 人）", "", "只在事件中登場、不能操作的角色。", "", *head]
        out += [row(p) for p in events]
    body = "\n".join(out).rstrip()
    return f"<!-- data:index begin -->\n{body}\n<!-- data:index end -->"


def main() -> None:
    people = load()
    old = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    block = index_block(people)
    if re.search(r"<!-- data:index begin -->", old):
        text = re.sub(r"<!-- data:index begin -->.*?<!-- data:index end -->", lambda _: block, old, flags=re.S)
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        created = m.group(1) if (m := re.search(r"^dateCreated: (\S+)", old, re.M)) else now
        text = "\n".join([
            "---", "title: 拿破崙時代", 'description: "《拿破崙》登場人物索引，依國籍分類。"',
            "published: true", f"date: {now}", "tags: lempe", "editor: markdown", f"dateCreated: {created}",
            "---", "",
            f"《[拿破崙](/遊戲/拿破崙)》登場的 {len(people)} 位人物，依遊戲中的國籍分類；"
            "條目名稱採遊戲中文版譯名。遊戲數值一覽見[人物資料](/遊戲/拿破崙/人物資料)。", "", block,
        ]) + "\n"
    if "--dry-run" not in sys.argv and text != old:
        INDEX.write_text(text, encoding="utf-8")
    print(f"{len(people)} people,", "unchanged" if text == old else "written")


if __name__ == "__main__":
    main()
