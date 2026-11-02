#!/usr/bin/env python3
"""Build Sanguo person entries (人物/三國/*.md) from the mapping and bio data.

Data blocks (<!-- data:x begin/end -->, EDITORIAL §10) are always regenerated.
A file that is still a Wiki.js stub ("Your content here") or missing is written
whole from the template layout; any other file only gets its data blocks replaced.

Inputs:
  assets/data/sanguo/persons-mapping.csv   wiki name -> game IDs per dataset
  assets/data/sanguo/sanguo-bios.jsonl     courtesy, faction, bio, refs
  assets/data/sanguo/persons-new.csv       faction and 出典 for entries without bios
  ~/works/kaodata-re/export/koei-wiki/stats/<dataset>.jsonl  optional, ID-keyed stats
  ~/.cache/koei-wiki/kaodata-faces/        index.json cache (build_sanguo_mapping.py)

Usage: scripts/build_sanguo_entries.py [--all | 名1 名2 ...] [--dry-run]
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/sanguo"
OUT_DIR = ROOT / "人物/三國"
STATS_DIR = Path.home() / "works/kaodata-re/export/koei-wiki/stats"  # not in git (kaodata-re export)
FACES = Path.home() / ".cache/koei-wiki/kaodata-faces"
IMG = "https://img.simagame.me/kaodata/faces/{}/{}.png"

MAINLINE = [  # (dataset, kbd label, title for alt text)
    ("san1-pc98", "三1", "三國志"), ("san2-pc98", "三2", "三國志II"),
    ("san3-pc98", "三3", "三國志III"), ("san4pk-pc98", "三4", "三國志IV"),
    ("san5pk-pc98", "三5", "三國志V"), ("san6pk-win", "三6", "三國志VI"),
    ("san7pk-win", "三7", "三國志VII"), ("san8pk-win", "三8", "三國志VIII"),
    ("san9pk-win", "三9", "三國志IX"), ("san10pk-win", "三10", "三國志X"),
    ("san11pk-win", "三11", "三國志11"), ("san12pk-win", "三12", "三國志12"),
    ("san13pk-win", "三13", "三國志13"), ("san14pk-win", "三14", "三國志14"),
]
KOEI = [  # (dataset, caption); order as decided with the user
    ("san1-fc", "三國志（FC）"), ("san2-fc", "三國志II（FC）"),
    ("san1-sfc", "超級三國志（SFC）"), ("san2-sfc", "超級三國志II（SFC）"),
    ("san1-x68", "三國志（X68000）"), ("eiketsu-pc98", "三國志英傑傳（PC-98）"),
]
STATS = ["統率", "武力", "智力", "政治", "魅力"]
# Stats a generation does not have (template's pre-filled —).
NO_STAT = {"三1": {"統率", "政治"}, "三2": {"統率", "政治"}, "三3": {"統率"},
           "三5": {"統率"}, "三7": {"統率"}, "三8": {"統率"},
           "三9": {"魅力"}, "三12": {"魅力"}, "三13": {"魅力"}}
# Game-native stat names -> main-table names.
STAT_ALIAS = {"知力": "智力", "カリスマ": "魅力"}

CELL_IMG = ('<figure style="margin: 0;">\n<img src="{src}" alt="{name} {title}" width="96" height="120" '
            'style="display: block; object-fit: contain; image-rendering: pixelated;">\n'
            "<figcaption><kbd>{kbd}</kbd></figcaption>\n</figure>")
CELL_EMPTY = ('<figure style="margin: 0;">\n<div style="width: 96px; height: 120px; background: #eee;"></div>\n'
              "<figcaption><kbd>{kbd}</kbd> 未登場</figcaption>\n</figure>")


def faces_index() -> dict[str, set[int]]:
    """dataset -> IDs that have at least one face."""
    out = {}
    for ds, _ in [(d, 0) for d, *_ in MAINLINE] + KOEI:
        rows = json.loads((FACES / f"{ds}.json").read_text(encoding="utf-8"))
        out[ds] = {r["id"] for r in rows if r.get("faces")}
    return out


def load_stats() -> dict[str, dict[int, dict]]:
    out = {}
    for ds, *_ in MAINLINE:
        path = STATS_DIR / f"{ds}.jsonl"
        if path.exists():
            out[ds] = {(r := json.loads(line))["id"]: {STAT_ALIAS.get(k, k): v for k, v in r["stats"].items()}
                       for line in path.read_text(encoding="utf-8").splitlines() if line}
    return out


def first_id(cell: str) -> int | None:
    return int(cell.split("|")[0]) if cell else None


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def portraits_mainline(name: str, row: dict, faces: dict) -> str:
    cells = []
    for ds, kbd, title in MAINLINE:
        i = first_id(row[ds])
        if i is not None and i in faces[ds]:
            cells.append(CELL_IMG.format(src=IMG.format(ds, i), name=name, title=title, kbd=kbd))
        else:
            cells.append(CELL_EMPTY.format(kbd=kbd))
    grid = '<div style="display: grid; grid-template-columns: repeat(7, 96px); gap: 12px 8px; overflow-x: auto;">'
    return block("portraits-mainline", grid + "\n" + "\n".join(cells) + "\n</div>")


def portraits_koei(name: str, row: dict, faces: dict) -> str | None:
    cells = []
    for ds, caption in KOEI:
        i = first_id(row[ds])
        if i is not None and i in faces[ds]:
            cells.append(f'<figure style="margin: 0;">\n<img src="{IMG.format(ds, i)}" alt="{name} {caption}" '
                         f'height="120" style="image-rendering: pixelated;">\n'
                         f"<figcaption>{caption}</figcaption>\n</figure>")
    if not cells:
        return None
    flex = '<div style="display: flex; align-items: flex-end; gap: 12px 8px; flex-wrap: wrap;">'
    return block("portraits-koei", flex + "\n" + "\n".join(cells) + "\n</div>")


def stats_main(row: dict, stats: dict) -> str:
    lines = ["<details open>", "<summary>歷代能力</summary>", "",
             "| 作品 | " + " | ".join(STATS) + " |", "| :---: |" + " :---: |" * len(STATS)]
    for ds, kbd, _ in MAINLINE:
        i = first_id(row[ds])
        if i is None:
            lines.append(f"| <kbd>{kbd}</kbd> | " + " | ".join(["未登場"] + [""] * (len(STATS) - 1)) + " |")
            continue
        got = stats.get(ds, {}).get(i, {})
        vals = ["—" if s in NO_STAT.get(kbd, ()) else str(got.get(s, "?")) for s in STATS]
        lines.append(f"| <kbd>{kbd}</kbd> | " + " | ".join(vals) + " |")
    lines += ["", "</details>"]
    body = "\n".join(lines)
    if not stats:
        body = "<!-- 數值待匯入（kaodata-re 能力值匯出），? 表示尚無資料 -->\n" + body
    return block("stats-main", body)


def plain(md: str) -> str:
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)


def title_of(wiki: str) -> str:
    base, _, tag = wiki.partition("_")
    return f"{base} ({tag})" if tag else base


def render_new(wiki: str, row: dict, bio: dict, extra: dict, blocks: dict, old: str) -> str:
    name = wiki.partition("_")[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = m.group(1) if (m := re.search(r"^dateCreated: (\S+)", old, re.M)) else now
    faction = (bio or {}).get("faction") or extra.get("勢力") or row["勢力"]
    source = extra.get("出典", "")
    tags = ", ".join(["三國"] + [s for s in re.split("[、,]", source) if s] + ([faction] if faction else []))
    text = (bio or {}).get("bio", "").strip()
    desc = plain(text.split("。")[0]) + "。" if text else ""
    out = ["---", f"title: {title_of(wiki)}", f'description: "{desc}"', "published: false",
           f"date: {now}", f"tags: {tags}", "editor: markdown", f"dateCreated: {created}", "---", "",
           "## 基本資料", "", "| 項目 | 內容 |", "| :--- | :--- |", f"| 姓名 | {name} |"]
    if bio and bio.get("courtesy"):
        out.append(f"| 字 | {bio['courtesy']} |")
    if faction:
        out.append(f"| 所屬 | {faction} |")
    if source:
        out.append(f"| 出典 | {source} |")
    out += ["", "## 人物畫像", "", "### 正傳", "", blocks["portraits-mainline"]]
    if "portraits-koei" in blocks:
        out += ["", "### 光榮其他作品", "", blocks["portraits-koei"]]
    out += ["", "## 遊戲數值", "", blocks["stats-main"], "", "## 列傳", "", text or "{列傳}"]
    refs = (bio or {}).get("refs") or []
    if refs:
        out += ["", "## References", ""] + [f"- [{name} - 维基百科]({u})" for u in refs]
    return "\n".join(out) + "\n"


def replace_blocks(text: str, blocks: dict) -> str:
    for key, body in blocks.items():
        pat = re.compile(rf"<!-- data:{key} begin -->.*?<!-- data:{key} end -->", re.S)
        text = pat.sub(lambda _: body, text)
    return text


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    mapping = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8"))}
    bios = {(r := json.loads(line))["name"]: r
            for line in open(DATA / "sanguo-bios.jsonl", encoding="utf-8") if line.strip()}
    new = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-new.csv", encoding="utf-8"))}
    names = list(mapping) if "--all" in sys.argv else args
    faces, stats = faces_index(), load_stats()
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    for wiki in names:
        row = mapping[wiki]
        name = wiki.partition("_")[0]
        blocks = {"portraits-mainline": portraits_mainline(name, row, faces),
                  "stats-main": stats_main(row, stats)}
        if (k := portraits_koei(name, row, faces)):
            blocks["portraits-koei"] = k
        path = OUT_DIR / f"{wiki}.md"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if not old or "Your content here" in old:
            text, kind = render_new(wiki, row, bios.get(wiki), new.get(wiki, {}), blocks, old), "new"
        else:
            text = replace_blocks(old, blocks)
            kind = "updated" if text != old else "unchanged"
        counts[kind] += 1
        if not dry and text != old:
            path.write_text(text, encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
