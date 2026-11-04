#!/usr/bin/env python3
"""Build Sanguo person entries (人物/三國/*.md) from the mapping and bio data.

Data blocks (<!-- data:x begin/end -->, EDITORIAL §10) are always regenerated.
A file that is still a Wiki.js stub ("Your content here") or missing is written
whole from the template layout; any other file only gets its data blocks replaced.

Inputs:
  assets/data/sanguo/persons-mapping.csv   wiki name -> game IDs per dataset
  assets/data/sanguo/sanguo-bios.jsonl     courtesy, faction, bio, refs
  assets/data/sanguo/sanguo-bios-claude.jsonl  rewrite (scripts/sanguo_bios_claude.py), used once it has a review:
                                           replaces bio, adds 演義中的形象, 出典 and the zh.wikipedia ref;
                                           in an already-built file it replaces those two sections only
  assets/data/sanguo/persons-new.csv       faction and 出典 for entries without bios
  ~/works/kaodata-re/export/koei-wiki/stats/<dataset>.jsonl  optional, ID-keyed stats
  ~/.cache/koei-wiki/kaodata-faces/        index.json cache (build_sanguo_mapping.py)

Usage: scripts/build_sanguo_entries.py [--all | 名1 名2 ...] [--dry-run] [--force]
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
DATA = ROOT / "assets/data/sanguo"
OUT_DIR = ROOT / "人物/三國"
STATS_DIR = Path.home() / "works/kaodata-re/export/koei-wiki/stats"  # not in git (kaodata-re export)
FACES = Path.home() / ".cache/koei-wiki/kaodata-faces"
TRAITS_CSV = Path.home() / "works/kaodata-re/MISC_TABLE/ROTK - Character Stats & Abilities.csv"
IMG = "https://img.simagame.me/kaodata/faces/{}/{}.png"

# (dataset, kbd label, portrait caption numeral as in the games' own galleries)
MAINLINE = [
    ("san1-pc98", "三1", "I"), ("san2-pc98", "三2", "II"), ("san3-pc98", "三3", "III"),
    ("san4pk-pc98", "三4", "IV"), ("san5pk-pc98", "三5", "V"), ("san6pk-win", "三6", "VI"),
    ("san7pk-win", "三7", "VII"), ("san8pk-win", "三8", "VIII"), ("san9pk-win", "三9", "IX"),
    ("san10pk-win", "三10", "X"), ("san11pk-win", "三11", "11"), ("san12pk-win", "三12", "12"),
    ("san13pk-win", "三13", "13"), ("san14pk-win", "三14", "14"),
]
MAINLINE_NOTE = "I–V 為 PC-98 版，VI–14 為 Windows 版；IV 以後為威力加強版。"
# (dataset, title, platform): grouped by original game (I, II, 英傑傳), then by the
# port's Japanese release date (kaodata src/ui/releases.ts).
KOEI = [
    ("san1-fc", "三國志", "FC"),            # 1988-10-30
    ("san1-x68", "三國志", "X68000"),       # 1988-12-09
    ("san1-sfc", "超級三國志", "SFC"),      # 1994-08-12
    ("san2-fc", "三國志II", "FC"),          # 1990-11-02
    ("san2-sfc", "超級三國志II", "SFC"),    # 1991-09-15
    ("eiketsu-pc98", "三國志英傑傳", "PC-98"),  # 1995-02
]
STATS = ["統率", "武力", "智力", "政治", "魅力"]
# Stats a generation does not have (template's pre-filled —).
NO_STAT = {"三1": {"統率", "政治"}, "三2": {"統率", "政治"}, "三3": {"統率"},
           "三5": {"統率"}, "三7": {"統率"}, "三8": {"統率"},
           "三9": {"魅力"}, "三12": {"魅力"}, "三13": {"魅力"}}
# Game-native stat names -> main-table names.
STAT_ALIAS = {"知力": "智力", "カリスマ": "魅力"}

# Layout lives in assets/wikijs/theme.css (Wiki.js CSS override); entries only carry class names.
CELL_IMG = ('<figure class="kw-face">\n<img src="{src}" alt="{name} {title}" width="96" height="120">\n'
            "<figcaption>{num}</figcaption>\n</figure>")
CELL_EMPTY = ('<figure class="kw-face">\n<div class="kw-absent">未登場</div>\n'
              "<figcaption>{num}</figcaption>\n</figure>")
GRID = '<div class="kw-portraits-mainline">'
FLEX = '<div class="kw-portraits">'



def faces_index() -> dict[str, set[int]]:
    """dataset -> IDs that have at least one face."""
    out = {}
    for ds in [d for d, *_ in MAINLINE] + [d for d, *_ in KOEI]:
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


def load_traits() -> dict[str, list[str]]:
    """wiki name -> extra tags (女性, 異民族 and the people's name) from the kaodata-re table."""
    out = {}
    for r in csv.DictReader(open(TRAITS_CSV, encoding="utf-8")):
        wiki = r["姓名"].replace(" (", "_").rstrip(")")
        tags = (["女性"] if r["女"] else []) + (["異民族", r["異民族"]] if r["異民族"] else [])
        if tags:
            out[wiki] = tags
    return out


def first_id(cell: str) -> int | None:
    return int(cell.split("|")[0]) if cell else None


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def portraits_mainline(name: str, row: dict, faces: dict) -> str:
    cells = []
    for ds, _, num in MAINLINE:
        i = first_id(row[ds])
        if i is not None and i in faces[ds]:
            cells.append(CELL_IMG.format(src=IMG.format(ds, i), name=name, num=num,
                                        title="三國志" + ("" if num == "I" else num)))
        else:
            cells.append(CELL_EMPTY.format(num=num))
    return block("portraits-mainline", GRID + "\n" + "\n".join(cells) + "\n</div>")


def portraits_koei(name: str, row: dict, faces: dict) -> str | None:
    cells = []
    for ds, title, platform in KOEI:
        i = first_id(row[ds])
        if i is not None and i in faces[ds]:
            cells.append(f'<figure class="kw-face">\n<img src="{IMG.format(ds, i)}" alt="{name} {title}（{platform}）" '
                         f'height="120">\n<figcaption>{title}<br>{platform}</figcaption>\n</figure>')
    if not cells:
        return None
    return block("portraits-koei", FLEX + "\n" + "\n".join(cells) + "\n</div>")


def stats_main(row: dict, stats: dict) -> str:
    lines = ['<details class="kw-stats" open>', "<summary>歷代能力</summary>", "",
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


def render_new(wiki: str, row: dict, bio: dict, extra: dict, traits: list, blocks: dict, old: str) -> str:
    name = wiki.partition("_")[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = m.group(1) if (m := re.search(r"^dateCreated: (\S+)", old, re.M)) else now
    faction = (bio or {}).get("faction") or extra.get("勢力") or row["勢力"]
    source = extra.get("出典") or (bio or {}).get("origin", "")
    tags = ", ".join(["三國"] + [s for s in re.split("[、,]", source) if s] + ([faction] if faction else []) + traits)
    text = (bio or {}).get("bio", "").strip()
    desc = plain(text.split("。")[0]) + "。" if text else ""
    out = ["---", f"title: {title_of(wiki)}", f'description: "{desc}"', "published: true",
           f"date: {now}", f"tags: {tags}", "editor: markdown", f"dateCreated: {created}", "---", "",
           "## 基本資料", "", "| 項目 | 內容 |", "| :--- | :--- |", f"| 姓名 | {name} |"]
    if bio and bio.get("courtesy"):
        out.append(f"| 字 | {bio['courtesy']} |")
    if faction:
        out.append(f"| 所屬 | {faction} |")
    if source:
        out.append(f"| 出典 | {source} |")
    out += ["", "## 人物畫像", "", "### 正傳", "", MAINLINE_NOTE, "", blocks["portraits-mainline"]]
    if "portraits-koei" in blocks:
        out += ["", "### 光榮其他作品", "", blocks["portraits-koei"]]
    out += ["", "## 遊戲數值", "", blocks["stats-main"], "", "## 列傳", "", text or "<!-- 列傳待補 -->"]
    if (bio or {}).get("yanyi"):
        out += ["", "## 演義中的形象", "", bio["yanyi"]]
    refs = (bio or {}).get("refs") or []
    if refs:
        out += ["", "## References", ""] + [f"- [{name} - 维基百科]({u})" for u in refs]
    return "\n".join(out) + "\n"


def wiki_url(title: str) -> str:
    return "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def merge_claude(bio: dict | None, claude: dict | None) -> dict | None:
    """Old bio record with the Claude rewrite's bio, yanyi, 出典 and wiki ref on top."""
    if not claude:
        return bio
    src = claude["sources"]
    origin = claude["origin"].replace("其他", "其他出典")
    if origin == "正史" and src.get("yanyi_text"):
        origin += "、演義"
    return {**(bio or {}), "bio": claude["bio"], "yanyi": claude["yanyi"], "origin": origin,
            "refs": [wiki_url(src["wikipedia"])] if src.get("wikipedia") else []}


def replace_section(text: str, heading: str, body: str, after: str) -> str:
    """Set the body of `## heading` (created right after section `after` if missing; removed if body is empty)."""
    pat = re.compile(rf"^## {heading}\n.*?(?=^## |\Z)", re.S | re.M)
    new = f"## {heading}\n\n{body}\n\n" if body else ""
    if pat.search(text):
        return pat.sub(lambda _: new, text, count=1).rstrip("\n") + "\n"
    if not body:
        return text
    m = re.search(rf"^## {after}\n.*?(?=^## |\Z)", text, re.S | re.M)
    return text[:m.end()] + new + text[m.end():] if m else text.rstrip("\n") + "\n\n" + new


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
    claude_path = DATA / "sanguo-bios-claude.jsonl"
    claude = {(r := json.loads(line))["name"]: r
              for line in open(claude_path, encoding="utf-8") if line.strip()} if claude_path.exists() else {}
    claude = {k: r for k, r in claude.items() if r.get("review")}  # unreviewed drafts are not published
    names = list(mapping) if "--all" in sys.argv else args
    faces, stats, traits = faces_index(), load_stats(), load_traits()
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
        if not old or "Your content here" in old or "--force" in sys.argv:
            bio = merge_claude(bios.get(wiki), claude.get(wiki))
            text = render_new(wiki, row, bio, new.get(wiki, {}), traits.get(wiki, []), blocks, old)
            kind = "new"
        else:
            text = replace_blocks(old, blocks)
            if wiki in claude:
                text = replace_section(text, "列傳", claude[wiki]["bio"], "遊戲中的登場")
                text = replace_section(text, "演義中的形象", claude[wiki]["yanyi"], "列傳")
            kind = "updated" if text != old else "unchanged"
        counts[kind] += 1
        if not dry and text != old:
            path.write_text(text, encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
