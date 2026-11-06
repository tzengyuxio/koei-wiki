#!/usr/bin/env python3
"""Generate the Suikoden 州 entries and the 州資料一覽 page (EDITORIAL §3.3 水滸州條目).

Reads the kaodata-re export suikoden-dos (koei-places/1, docs/places-format.mkdn) and, when present,
assets/data/suikoden/place-entries.jsonl (per-entry facts and intro, written by
sanguo_places_batch.py --set suikoden).

New files get the full template; existing files only get their data blocks replaced (EDITORIAL §10).

Suikoden person and 州 names in the intros link to their entries, first mention only (EDITORIAL §6).

Usage: python3 scripts/build_suikoden_places.py [--dry-run] [--force]
  --force  rewrite whole files, not only the data blocks (loses hand edits)
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

from build_sanguo_places import block, front, keep_created, link_intro, replace_blocks

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/suikoden"
OUT = Path(os.environ.get("KOEI_OUT", ROOT))
EXPORT = Path(os.environ.get("PLACES_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/places"))
GAME = "水滸傳・天命之誓"
TYPOS = {"窿德": "隆德", "鳳祥": "鳳翔", "穎州": "潁州"}  # game writing -> historical name


def sanguo_names() -> set[str]:
    """Names taken by Sanguo place / 州 entries (built or not yet built)."""
    sg = ROOT / "assets/data/sanguo"
    names = {r["entry"] for r in csv.DictReader((sg / "places.csv").open(encoding="utf-8")) if r["entry"]}
    return names | {r["entry"] for r in csv.DictReader((sg / "places-provinces.csv").open(encoding="utf-8")) if r["entry"]}


def entries() -> list[dict]:
    """One dict per 州: the export row plus entry name, file name and the Sanguo page it collides with."""
    rows = [json.loads(line) for line in (EXPORT / "suikoden-dos.jsonl").read_text(encoding="utf-8").splitlines() if line]
    sg = sanguo_names()
    for p in rows:
        p["entry"] = TYPOS.get(p["name"], p["name"])
        p["sanguo"] = p["entry"] in sg
        p["file"] = f"{p['entry']}_水滸" if p["sanguo"] else p["entry"]
    return rows


def main() -> None:
    dry = "--dry-run" in sys.argv
    rows = entries()
    by_id = {p["id"]: p for p in rows}
    facts = {}
    if (DATA / "place-entries.jsonl").exists():
        for line in (DATA / "place-entries.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                facts[json.loads(line)["entry"]] = json.loads(line)
    link = lambda p: f"[{p['entry']}](/地點/{p['file']})"  # noqa: E731
    written = 0
    force = "--force" in sys.argv
    targets = {f.stem: f"/人物/水滸/{f.stem}" for f in (ROOT / "人物/水滸").glob("*.md") if "_" not in f.stem}
    targets.update({p["entry"]: f"/地點/{p['file']}" for p in rows})

    def write(path: Path, new_text: str, blocks: dict[str, str]) -> None:
        nonlocal written
        old = path.read_text(encoding="utf-8") if path.exists() else None
        text = new_text if old is None else keep_created(old, new_text) if force else replace_blocks(old, blocks)
        if not path.exists() or text != path.read_text(encoding="utf-8"):
            written += 1
            if not dry:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    for p in rows:
        table = "\n".join(["| 項目 | 內容 |", "| :--- | :--- |", f"| 編號 | {p['id']} |", f"| 城數 | {p['cities']} |",
                           f"| 相鄰 | {'、'.join(link(by_id[a]) for a in p['adjacent'])} |"])
        write(OUT / "地點" / f"{p['file']}.md", render(p, table, facts.get(p["entry"], {}), targets),
              {"suikoden-places-main": table})

    index = ["| 編號 | 州 | 城數 | 相鄰 |", "| ---: | :--- | ---: | :--- |"]
    for p in rows:
        shown = link(p) + (f"（{p['name']}）" if p["name"] != p["entry"] else "")
        index.append(f"| {p['id']} | {shown} | {p['cities']} | {'、'.join(link(by_id[a]) for a in p['adjacent'])} |")
    index = "\n".join(index)
    summary = facts.get(f"遊戲:{GAME}", {}).get("summary") or "{概要}"
    page = "\n\n".join([front(f"{GAME} 州資料一覽", f"{GAME}的 49 州一覽", "水滸, suikoden, 地點"),
                        "## 概要\n\n" + summary,
                        "## 州一覽\n\n" + block("places-index", index),
                        "## 資料來源\n\n- kaodata-re 匯出（koei-places/1，資料集 suikoden-dos）"]) + "\n"
    write(OUT / "遊戲" / GAME / "州資料一覽.md", page, {"places-index": index})
    print(f"{'would write' if dry else 'wrote'} {written} files")


def render(p: dict, table: str, f: dict, targets: dict[str, str]) -> str:
    e = p["entry"]
    title = f"{e} (水滸)" if p["sanguo"] else e
    rows = [f"| 名稱 | {e} |"]
    for key, label in (("song_division", "北宋政區"), ("seat", "治所"), ("today", "今地")):
        if f.get(key):
            rows.append(f"| {label} | {f[key]} |")
    writing = []
    if p["name"] != e:
        writing.append(f"{p['name']}（<kbd>水</kbd>，遊戲中的錯字）")
    if p.get("nameJa"):
        writing.append(f"日文版 {p['nameJa']}")
    if writing:
        rows.append("| 遊戲寫法 | " + "；".join(writing) + " |")
    m = re.search(r"城數：[^；。]*", p.get("notes", ""))  # version differences, e.g. 延安
    note = m.group(0) + "。" if m else ""
    parts = [front(title, f.get("description") or f"{GAME}中的州：{e}", "水滸, 地點, suikoden")]
    if p["sanguo"]:
        parts.append(f"> 三國志系列的同名地點見 [{e}](/地點/{e})。")
    parts += ["## 基本資料\n\n| 項目 | 內容 |\n| :--- | :--- |\n" + "\n".join(rows),
              "## 遊戲中的地點資料\n\n" + block("suikoden-places-main", table) + (f"\n\n{note}" if note else ""),
              "## 簡介\n\n" + (link_intro(f["intro"], e, targets) if f.get("intro") else "{簡介}")]
    if f.get("events"):
        parts.append("## 水滸傳中的事件\n\n" + "\n".join(f"- {ev}" for ev in f["events"]))
    titles = f.get("refs") or []
    if titles:
        parts.append("## References\n\n" + "\n".join(
            f"- [{t} - 维基百科](https://zh.wikipedia.org/wiki/{t.replace(' ', '_')})" for t in titles))
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    main()
