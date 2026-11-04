#!/usr/bin/env python3
"""Count the site's entries and write them into home.md and 統計.md (data blocks, EDITORIAL §10).

Counts only real pages: a Wiki.js stub ("Your content here") or a page with published: false is left out.

Usage: scripts/site_stats.py [--dry-run]
"""

import collections
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("assets", "docs", "node_modules")
ERAS = [("三國", "人物/三國"), ("水滸", "人物/水滸"), ("拿破崙時代", "人物/拿破崙時代"), ("秦漢之際", "人物/秦漢之際")]
SECTIONS = [("地點", "地點"), ("用語", "用語"), ("事件", "事件")]
FACTIONS = ["曹魏", "蜀漢", "東吳", "群雄"]


def pages() -> dict[str, str]:
    out = {}
    for f in ROOT.rglob("*.md"):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(SKIP) or "/" not in rel and rel != "home.md":
            continue
        out[rel] = f.read_text(encoding="utf-8")
    return out


def is_real(text: str) -> bool:
    return "Your content here" not in text and not re.search(r"^published: false", text, re.M)


def tags(text: str) -> list[str]:
    m = re.search(r"^tags:\s*(.*)$", text, re.M)
    return [t.strip() for t in m.group(1).split(",")] if m else []


def field(text: str, key: str) -> str:
    m = re.search(rf"^\| {key} \| (.*?) \|", text, re.M)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1)) if m else ""


def in_dir(rel: str, d: str) -> bool:
    return rel.startswith(d + "/") and rel.count("/") == d.count("/") + 1


def collect() -> dict:
    all_pages = pages()
    real = {p: t for p, t in all_pages.items() if is_real(t)}
    s = {"era": {}, "section": {}}
    for label, d in ERAS:
        s["era"][label] = {p: t for p, t in real.items() if in_dir(p, d)}
    for label, d in SECTIONS:
        s["section"][label] = sum(1 for p in real if in_dir(p, d))
    s["sanguo_pending"] = sum(1 for p, t in all_pages.items() if in_dir(p, "人物/三國") and not is_real(t))
    s["games"] = sum(1 for p in real if in_dir(p, "遊戲"))
    s["game_pages"] = sum(1 for p in real if p.startswith("遊戲/"))
    imgs = collections.defaultdict(set)
    for t in real.values():
        for src in re.findall(r'<img src="([^"]+)"', t) + re.findall(r"!\[[^\]]*\]\(([^)\s]+)", t):
            kind = ("game" if "img.simagame.me" in src or "/faces/" in src
                    else "portrait" if "/portraits/" in src else "map" if "/maps/" in src else None)
            if kind:
                imgs[kind].add(src)
    s["images"] = {k: len(v) for k, v in imgs.items()}
    return s


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def summary(s: dict) -> str:
    era = {k: len(v) for k, v in s["era"].items()}
    rows = [f"| 三國人物 | {era['三國']}（陸續上架中） |", f"| 水滸人物 | {era['水滸']} |",
            f"| 拿破崙時代人物 | {era['拿破崙時代']} |", f"| 秦漢之際人物 | {era['秦漢之際']} |",
            f"| 地點、用語、事件 | {sum(s['section'].values())} |", f"| 遊戲介紹 | {s['games']} 款 |",
            f"| 遊戲頭像、歷史肖像、地圖 | {sum(s['images'].values())} 張 |"]
    return "\n".join(["| 項目 | 數量 |", "| :--- | ---: |", *rows])


def counter_table(head: str, counts: collections.Counter, order: list[str] | None = None) -> list[str]:
    keys = order or [k for k, _ in counts.most_common()]
    return [f"| {head} | 人數 |", "| :--- | ---: |", *[f"| {k} | {counts[k]} |" for k in keys if counts[k]]]


def full(s: dict) -> str:
    era = s["era"]
    out = [f"統計日期：{date.today().isoformat()}。只計已完成的頁面，不含尚未撰寫的空白頁。", "",
           "## 條目數", "", "| 分類 | 條目數 |", "| :--- | ---: |"]
    out += [f"| [{k}人物](/人物/{k}) | {len(v)} |" if k != "三國" else f"| 三國人物 | {len(v)} |" for k, v in era.items()]
    out += [f"| {k} | {n} |" for k, n in s["section"].items()]
    out += [f"| 遊戲介紹 | {s['games']} 款（含子頁面共 {s['game_pages']} 頁） |", "",
            f"三國人物另有 {s['sanguo_pending']} 位已建立頁面、列傳待上架。", ""]

    sg = era["三國"].values()
    out += ["## 三國人物", "", "### 所屬勢力", ""]
    out += counter_table("勢力", collections.Counter(field(t, "所屬") for t in sg), FACTIONS)
    origin = collections.Counter()
    for t in sg:
        src = field(t, "出典")
        origin["正史、演義皆有" if "正史" in src and "演義" in src else "僅見正史" if "正史" in src
               else "演義虛構" if "演義" in src else "其他出典" if src else "未標示"] += 1
    out += ["", "### 出典", ""] + counter_table("出典", origin)
    traits = collections.Counter(tg for t in sg for tg in tags(t) if tg in ("女性", "異民族"))
    out += ["", "### 其他", "", "| 項目 | 人數 |", "| :--- | ---: |",
            f"| 有「演義中的形象」一段 | {sum('## 演義中的形象' in t for t in sg)} |",
            f"| 女性 | {traits['女性']} |", f"| 異民族 | {traits['異民族']} |", ""]

    sh = collections.Counter(next((x for x in ("天罡星", "地煞星") if x in tags(t)), "其他人物") for t in era["水滸"].values())
    out += ["## 水滸人物", ""] + counter_table("分類", sh, ["天罡星", "地煞星", "其他人物"]) + [""]

    nat = collections.Counter(field(t, "國籍") or "未詳" for t in era["拿破崙時代"].values())
    out += ["## 拿破崙時代人物", "", "依國籍：", ""] + counter_table("國籍", nat) + [""]

    im = s["images"]
    out += ["## 圖片", "", "| 種類 | 張數 |", "| :--- | ---: |", f"| 遊戲頭像 | {im.get('game', 0)} |",
            f"| 歷史肖像 | {im.get('portrait', 0)} |", f"| 地圖 | {im.get('map', 0)} |"]
    return "\n".join(out)


def put(path: Path, name: str, body: str, dry: bool) -> None:
    text = path.read_text(encoding="utf-8")
    pat = re.compile(rf"<!-- data:{name} begin -->.*?<!-- data:{name} end -->", re.S)
    if not pat.search(text):
        sys.exit(f"{path.name}: no data:{name} block")
    new = pat.sub(lambda _: block(name, body), text)
    if new != text and not dry:
        path.write_text(new, encoding="utf-8")
    print(f"{path.name}: {'changed' if new != text else 'unchanged'}")


def main() -> None:
    dry = "--dry-run" in sys.argv
    s = collect()
    put(ROOT / "home.md", "site-stats-summary", summary(s), dry)
    put(ROOT / "統計.md", "site-stats", full(s), dry)


if __name__ == "__main__":
    main()
