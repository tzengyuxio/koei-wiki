#!/usr/bin/env python3
"""Build Nobunaga person entries (人物/日本戰國/*.md) from the mapping and the kaodata-re export.

Design: docs/backlog/nobunaga-persons.mkdn; template: assets/person_nobunaga_template.mkdn.
Data blocks (<!-- data:x begin/end -->, EDITORIAL §10) are always regenerated. A missing file (or a
Wiki.js stub, or any file with --force) is written whole; otherwise only its data blocks are replaced.

Inputs:
  assets/data/nobunaga/persons-mapping.csv   wiki name -> game IDs per dataset (build_nobunaga_mapping.py)
  ~/works/kaodata-re/export/koei-wiki/persons/<dataset>.jsonl   (koei-persons/1)
  https://img.simagame.me/kaodata/faces/<dataset>/index.json   cached in ~/.cache/koei-wiki/kaodata-faces/
  ja.wikipedia titles for References, cached in ~/.cache/koei-wiki/nobunaga-jawiki.json

Usage: python3 scripts/build_nobunaga_entries.py [--first-batch | 名1 名2 ...] [--dry-run] [--force]
"""

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from build_nobunaga_mapping import DATASETS, to_tw

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/nobunaga"
OUT_DIR = ROOT / "人物/日本戰國"
EXPORT = Path(os.environ.get("KOEI_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki")) / "persons"
CACHE = Path.home() / ".cache/koei-wiki"
IMG = "https://img.simagame.me/kaodata/faces/{}/{}.png"

# dataset -> (kbd, caption, full title)
GAMES = {
    "nobu2-pc88": ("信2", "全國版", "信長之野望・全國版"),
    "nobu3-pc98": ("信3", "群雄傳", "信長之野望・戰國群雄傳"),
    "nobu4-pc98": ("信4", "風雲錄", "信長之野望・武將風雲錄"),
    "nobu5pk-win": ("信5", "霸王傳", "信長之野望・霸王傳"),
    "nobu6pk-pc98": ("信6", "天翔記", "信長之野望・天翔記"),
    "nobu7pk-win": ("信7", "將星錄", "信長之野望・將星錄"),
    "nobu8pk-win": ("信8", "烈風傳", "信長之野望・烈風傳"),
    "nobu9pk-win": ("信9", "嵐世記", "信長之野望・嵐世記"),
    "nobu10pk-win": ("信10", "蒼天錄", "信長之野望・蒼天錄"),
    "nobu11pk-win": ("信11", "天下創世", "信長之野望・天下創世"),
    "nobu12pk-win": ("信12", "革新", "信長之野望・革新"),
    "nobu13pk-win": ("信13", "天道", "信長之野望・天道"),
}
MAINLINE_NOTE = "信2 為 PC-88 版，信3、信4、信6 為 PC-98 版，其餘為 Windows 版；信5 以後為威力加強版。"
STATS = ["政治", "統率", "武勇", "智謀", "魅力", "野望"]
STAT_OF = {"政治力": "政治", "政治": "政治", "采配": "統率", "統率": "統率", "戦闘力": "武勇", "戦闘": "武勇",
           "武勇": "武勇", "ＩＱ": "智謀", "智謀": "智謀", "知謀": "智謀", "知略": "智謀", "魅力": "魅力",
           "野望": "野望", "野心": "野望"}  # EDITORIAL §3.1; 健康, 運, 教養 are not shown
RELATIONS = [("father", "父"), ("mother", "母"), ("spouse", "配偶"), ("sworn", "義兄弟"), ("siblings", "兄弟姊妹"),
             ("children", "子女")]
CELL_IMG = ('<figure class="kw-face">\n<img src="{src}" alt="{name} {title}" width="96" height="120">\n'
            "<figcaption>{cap}</figcaption>\n</figure>")
CELL_TEXT = '<figure class="kw-face">\n<div class="kw-absent">{text}</div>\n<figcaption>{cap}</figcaption>\n</figure>'


def load_persons() -> dict[str, dict[int, dict]]:
    out = {}
    for ds in DATASETS:
        rows = [json.loads(line) for line in (EXPORT / f"{ds}.jsonl").read_text(encoding="utf-8").splitlines() if line]
        out[ds] = {r["id"]: r for r in rows}
    return out


def faces_index() -> dict[str, set[int]]:
    out = {}
    for ds in DATASETS:
        path = CACHE / "kaodata-faces" / f"{ds}.json"
        if not path.exists():
            req = urllib.request.Request(f"https://img.simagame.me/kaodata/faces/{ds}/index.json",
                                         headers={"User-Agent": "koei-wiki-build"})  # Cloudflare 403s urllib's default
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read()
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                body = b"[]"  # not uploaded yet
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        out[ds] = {p["id"] for p in json.loads(path.read_text(encoding="utf-8"))}
    return out


def jawiki_titles(names: list[str]) -> dict[str, str | None]:
    """Japanese name -> ja.wikipedia article title (after redirects), None if there is no article."""
    path = CACHE / "nobunaga-jawiki.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = sorted({n for n in names if n not in cache})
    for i in range(0, len(todo), 40):
        part = todo[i:i + 40]
        q = urllib.parse.urlencode({"action": "query", "titles": "|".join(part), "redirects": 1,
                                "prop": "pageprops", "format": "json"})
        req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + q, headers={"User-Agent": "koei-wiki-build"})
        for wait in (0, 5, 15, 30, 60):  # ja.wikipedia answers 429 to quick bursts
            time.sleep(wait or 1)
            try:
                d = json.load(urllib.request.urlopen(req, timeout=30))["query"]
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
        else:
            sys.exit("ja.wikipedia keeps answering 429; run again later (finished batches are cached)")
        norm = {x["from"]: x["to"] for x in d.get("normalized", [])}
        red = {x["from"]: x["to"] for x in d.get("redirects", [])}
        pages = {p["title"]: p for p in d["pages"].values()}
        for n in part:
            t = red.get(norm.get(n, n), norm.get(n, n))
            p = pages.get(t, {})
            cache[n] = None if "missing" in p or "disambiguation" in p.get("pageprops", {}) else t
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    return cache


def wiki_api(**params) -> dict:
    q = urllib.parse.urlencode({"action": "query", "format": "json", **params})
    req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + q, headers={"User-Agent": "koei-wiki-build"})
    for wait in (1, 5, 15, 30, 60):
        time.sleep(wait)
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))["query"]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    sys.exit("ja.wikipedia keeps answering 429; run again later")


def disambiguated_title(ja: str, born: int | None, died: int | None) -> str | None:
    """When ja is a disambiguation page, the linked article whose intro has the birth and death years."""
    path = CACHE / "nobunaga-jawiki-disambig.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    key = f"{ja}|{born}|{died}"
    if key not in cache:
        pages = wiki_api(titles=ja, prop="links", pllimit="max")["pages"].values()
        links = [x["title"] for p in pages for x in p.get("links", [])]
        cands = [t for t in links if t.startswith((ja + " (", ja + "（"))]
        best, score = None, 0
        # the years sit in the infobox, so the intro alone has none; read the whole text. Articles under
        # another name (三好政勝 -> 三好為三) are tried last and must match both years.
        others = [t for t in links if t not in cands and t.startswith(ja[:2]) and not t.endswith(("氏", "家"))
                  and ":" not in t][:15] if born and died else []
        for c, need in [(c, 1) for c in cands[:10]] + [(c, 2) for c in others]:
            if best and need == 2:
                break
            text = next(iter(wiki_api(titles=c, prop="extracts", explaintext=1)["pages"].values())).get("extract", "")
            s = sum(any(f"{y + d}年" in text for d in (-1, 0, 1)) for y in (born, died) if y)
            if s >= need and s > score:
                best, score = c, s
        cache[key] = best
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    return cache[key]


def jawiki_title(ja: str, recs: dict, titles: dict) -> str | None:
    if t := titles.get(ja):
        return t
    born = next((r["born"] for r in reversed(list(recs.values())) if r.get("born")), None)
    died = next((r["died"] for r in reversed(list(recs.values())) if r.get("died")), None)
    return disambiguated_title(ja, born, died)


# Entries whose lookup lands on a namesake from another era: wiki名 -> the right title (None: no article).
JAWIKI_FIX = {"織田信行": "織田信行", "白河義綱": "結城義綱", "岩城常隆_2": None, "真里谷信保": "真里谷恕鑑"}


def person_title(wiki: str, ja: str, recs: dict, titles: dict | None = None) -> str | None:
    """The person's ja.wikipedia title: the game's Japanese name first, then the entry name."""
    if wiki in JAWIKI_FIX:
        return JAWIKI_FIX[wiki]
    name = wiki.partition("_")[0]
    return jawiki_title(ja, recs, titles or jawiki_titles([ja])) or jawiki_title(name, recs, jawiki_titles([name]))


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def records(row: dict, persons: dict) -> dict[str, dict]:
    """dataset -> the person's record there (first id when the game has several)."""
    return {ds: persons[ds][int(row[ds].split("|")[0])] for ds in DATASETS if row[ds]}


def kbd_list(dss: list[str]) -> str:
    return "、".join(f"<kbd>{GAMES[d][0]}</kbd>" for d in dss)


def ja_name(name: str, recs: dict, tw: dict) -> str:
    """The Japanese spelling of the entry name (細川藤孝, not the later 細川幽斎), newest game first."""
    jas = [r.get("nameJa") or r["name"] for r in reversed(list(recs.values()))]
    return next((j for j in jas if tw.get(j, j) == name), jas[0])


def basic(wiki: str, recs: dict, owner: dict, tw: dict) -> str:
    name = wiki.partition("_")[0]
    ja = ja_name(name, recs, tw)
    reading = next((r["reading"] for r in reversed(list(recs.values()))
                    if r.get("reading") and (r.get("nameJa") or r["name"]) == ja), "")
    born = next((r["born"] for r in reversed(list(recs.values())) if r.get("born")), None)
    died = next((r["died"] for r in reversed(list(recs.values())) if r.get("died")), None)
    rows = ["| 項目 | 內容 |", "| :--- | :--- |", f"| 姓名 | {name} |",
            f"| 日文 | {ja}" + (f"（{reading}）" if reading else "") + " |"]
    if born or died:
        rows.append(f"| 生卒 | {born or '不詳'}–{died or '不詳'} |")
    lords = main_lords(recs, owner)
    if lords:
        rows.append("| 主君 | " + " → ".join(link(x) if x != "大名" else x for x in lords) + " |")
    spellings = {}
    for ds, r in recs.items():
        if tw.get(r["name"], r["name"]) != name:
            spellings.setdefault(r["name"], []).append(ds)
    if spellings:
        rows.append("| 遊戲寫法 | " + "；".join(f"{n}（{kbd_list(d)}）" for n, d in spellings.items()) + " |")
    return block("basic", "\n".join(rows))


def main_lords(recs: dict, owner: dict) -> list[str]:
    """Lords across the games, ordered by the median scenario year.

    Later games add hypothetical scenarios (信13 makes 秀吉 a daimyo in 1565), so one game is not enough:
    a lord is kept when at least a quarter of the games with lord data (and at least two) agree.
    """
    seen: dict[str, dict[str, list[int]]] = {}  # lord -> dataset -> years
    games = 0
    for ds, r in recs.items():
        scen = [s for s in r.get("scenarios", []) if "lord" in s]
        games += bool(scen)
        for s in scen:
            who = "大名" if s["lord"] == r["id"] else owner.get((ds, s["lord"]))
            if who:
                seen.setdefault(who, {}).setdefault(ds, []).append(s.get("year") or 0)
    need = max(2, -(-games // 4)) if games > 1 else 1
    kept = []
    for who, by_ds in seen.items():
        if len(by_ds) >= need:
            years = sorted(y for ys in by_ds.values() for y in ys)
            kept.append((years[len(years) // 2], who))
    return [who for _, who in sorted(kept)]


EXISTING: set[str] = set()


def link(wiki: str) -> str:
    base = wiki.partition("_")[0]
    return f"[{base}](/人物/日本戰國/{wiki})" if wiki in EXISTING else base


def portraits(name: str, recs: dict, faces: dict) -> str:
    cells = []
    for ds, (kbd, short, title) in GAMES.items():
        cap = f"{short}（{kbd.removeprefix('信')}）"
        if ds not in recs:
            cells.append(CELL_TEXT.format(text="未登場", cap=cap))
        elif recs[ds]["id"] in faces[ds]:
            cells.append(CELL_IMG.format(src=IMG.format(ds, recs[ds]["id"]), name=name, title=title, cap=cap))
        else:
            cells.append(CELL_TEXT.format(text="待補", cap=cap))
    return block("portraits-mainline", '<div class="kw-portraits-mainline">\n' + "\n".join(cells) + "\n</div>")


def stats(recs: dict) -> str:
    lines = ['<details class="kw-stats" open>', "<summary>歷代能力</summary>", "",
             "| 作品 | " + " | ".join(STATS) + " |", "| :---: |" + " :---: |" * len(STATS)]
    for ds, (kbd, _, _) in GAMES.items():
        if ds not in recs:
            lines.append(f"| <kbd>{kbd}</kbd> | 未登場 |" + " |" * (len(STATS) - 1))
            continue
        got = {STAT_OF[k]: v for k, v in recs[ds].get("stats", {}).items() if k in STAT_OF}
        lines.append(f"| <kbd>{kbd}</kbd> | " + " | ".join(str(got.get(s, "—")) for s in STATS) + " |")
    return block("stats-main", "\n".join(lines + ["", "</details>"]))


def relations(recs: dict, owner: dict) -> str | None:
    ds = next((d for d in reversed(list(recs)) if recs[d].get("relations", {}).keys() - {"clan"}), None)
    if not ds:
        return None
    rel = recs[ds]["relations"]
    out = []
    for key, label in RELATIONS:
        names = [owner[(ds, i)] for i in rel.get(key, []) if (ds, i) in owner]
        if names:
            out.append(f"- {label}：" + "、".join(link(n) for n in names))
    return block("relations", "\n".join(out)) if out else None


def replace_blocks(text: str, blocks: dict) -> str:
    for key, body in blocks.items():
        text = re.sub(rf"<!-- data:{key} begin -->.*?<!-- data:{key} end -->", lambda _: body, text, flags=re.S)
    return text


def render(wiki: str, row: dict, recs: dict, blocks: dict, ja_title: str | None, old: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = m.group(1) if (m := re.search(r"^dateCreated: (\S+)", old, re.M)) else now
    base, _, tag = wiki.partition("_")
    gens = [GAMES[d][0] for d in recs]
    tags = ["日本戰國", "信長之野望"] + (["大名"] if row["大名"] else [])
    out = ["---", f"title: {base} ({tag})" if tag else f"title: {base}",
           f'description: "日本戰國時代的人物，在《信長之野望》{len(gens)} 代登場。"', "published: true",
           f"date: {now}", f"tags: {', '.join(tags)}", "editor: markdown", f"dateCreated: {created}", "---", "",
           "## 基本資料", "", blocks["basic"], "", "## 人物畫像", "", "### 正傳", "", MAINLINE_NOTE, "",
           blocks["portraits-mainline"], "", "## 遊戲數值", "", blocks["stats-main"], "",
           "## 列傳", "", "<!-- 列傳待補 -->"]
    if "relations" in blocks:
        out += ["", "## 相關人物", "", blocks["relations"]]
    if ja_title:
        url = "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(ja_title.replace(" ", "_"))
        out += ["", "## References", "", f"- [{ja_title} - Wikipedia（日本語）]({url})"]
    return "\n".join(out) + "\n"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    mapping = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8"))}
    names = [w for w, r in mapping.items() if r["第一批"]] if "--first-batch" in sys.argv else args
    persons, faces = load_persons(), faces_index()
    owner = {(ds, int(i)): w for w, r in mapping.items() for ds in DATASETS for i in r[ds].split("|") if i}
    EXISTING.update(p.stem for p in OUT_DIR.glob("*.md"))
    EXISTING.update(names)
    game_names = sorted({n for ds in persons.values() for p in ds.values() for n in (p["name"], p.get("nameJa")) if n})
    tw = dict(zip(game_names, to_tw(game_names)))
    all_recs = {w: records(mapping[w], persons) for w in names}
    jas = {w: ja_name(w.partition("_")[0], r, tw) for w, r in all_recs.items()}
    titles = jawiki_titles(list(jas.values()))
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    for wiki in names:
        recs = all_recs[wiki]
        name = wiki.partition("_")[0]
        blocks = {"basic": basic(wiki, recs, owner, tw), "portraits-mainline": portraits(name, recs, faces),
                  "stats-main": stats(recs)}
        if rel := relations(recs, owner):
            blocks["relations"] = rel
        path = OUT_DIR / f"{wiki}.md"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if not old or "Your content here" in old or "--force" in sys.argv:
            text = render(wiki, mapping[wiki], recs, blocks, person_title(wiki, jas[wiki], recs, titles), old)
            kind = "new"
        else:
            text = replace_blocks(old, blocks)
            kind = "updated" if text != old else "unchanged"
        counts[kind] += 1
        if not dry and text != old:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
