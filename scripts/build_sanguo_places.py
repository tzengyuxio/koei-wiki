#!/usr/bin/env python3
"""Generate Sanguo place entries, 州 entries and per-game city lists (EDITORIAL §3.3).

Reads the kaodata-re export (koei-places/1), the mapping tables from build_sanguo_places_csv.py and,
when present, assets/data/sanguo/place-entries.jsonl (per-entry facts and intro, one JSON per line:
{"entry", "han_division", "han_level", "han_province", "today", "intro", "events", "refs"}).

New files get the full template; existing files only get their data blocks replaced (EDITORIAL §10).

Person and place names in the intros link to their entries, first mention only (EDITORIAL §6).

Usage: python3 scripts/build_sanguo_places.py [--dry-run] [--force]
  --force  rewrite whole files, not only the data blocks (loses hand edits)
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/sanguo"
OUT = Path(os.environ.get("KOEI_OUT", ROOT))  # write somewhere else for a preview
EXPORT = Path(os.environ.get("PLACES_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/places"))

GAMES = [  # dataset, kbd, game folder / title, tag
    ("san1-pc98", "三1", "三國志", "san1"), ("san2-pc98", "三2", "三國志II", "san2"),
    ("san3-pc98", "三3", "三國志III", "san3"), ("san4pk-pc98", "三4", "三國志IV", "san4"),
    ("san5pk-pc98", "三5", "三國志V", "san5"), ("san6pk-win", "三6", "三國志VI", "san6"),
    ("san7pk-win", "三7", "三國志VII", "san7"), ("san8pk-win", "三8", "三國志VIII", "san8"),
    ("san9pk-win", "三9", "三國志IX", "san9"), ("san10pk-win", "三10", "三國志X", "san10"),
    ("san11pk-win", "三11", "三國志11", "san11"), ("san12pk-win", "三12", "三國志12", "san12"),
    ("san13pk-win", "三13", "三國志13", "san13"), ("san14pk-win", "三14", "三國志14", "san14"),
]
KBD = {g[0]: g[1] for g in GAMES}
LEVEL_GLYPH = str.maketrans({"関": "關", "拠": "據", "戦": "戰", "異": "異"})
DIFF_NOTE = {"typo": "，遊戲中的錯字", "alias": "", "glyph": ""}
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def keep_created(old: str, new: str) -> str:
    """A rewritten page keeps its original dateCreated."""
    m = re.search(r"^dateCreated: .*$", old, re.M)
    return re.sub(r"^dateCreated: .*$", lambda _: m.group(0), new, count=1, flags=re.M) if m else new


def replace_blocks(text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pat = re.compile(rf"<!-- data:{name} begin -->.*?<!-- data:{name} end -->", re.S)
        text = pat.sub(lambda _: block(name, body), text)
    return text


def load():
    export = {ds: {p["id"]: p for p in map(json.loads, (EXPORT / f"{ds}.jsonl").read_text(encoding="utf-8").splitlines())}
              for ds, *_ in GAMES}
    rows = list(csv.DictReader((DATA / "places.csv").open(encoding="utf-8")))
    provs = {(r["dataset"], r["game_name"]): r for r in csv.DictReader((DATA / "places-provinces.csv").open(encoding="utf-8"))}
    facts = {}
    if (DATA / "place-entries.jsonl").exists():
        for line in (DATA / "place-entries.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                f = json.loads(line)
                facts[f["entry"]] = f
    return export, rows, provs, facts


def file_names(entries: set[str], prov_entries: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Place entry -> page under 地點/, and 州 entry -> page. A 州 and a city with the same name: the city
    is <name>_都市. A people's 州 shares the place page. Names taken by other eras get _三國."""
    taken = {p.stem for p in (ROOT / "地點").glob("*.md") if not p.stem.endswith(("_都市", "_水滸"))} - entries - prov_entries
    era = lambda name: f"{name}_三國" if name in taken else name  # noqa: E731
    files = {e: era(f"{e}_都市" if e in prov_entries and not is_people(e) else e) for e in entries}
    pfiles = {e: files[e] if is_people(e) and e in files else era(e) for e in prov_entries}
    return files, pfiles


PEOPLES = {"倭", "氐", "羌", "南蠻", "山越", "烏丸", "鮮卑", "匈奴"}


def is_people(e: str) -> bool:
    return e in PEOPLES


# Place names that also read as ordinary words, or name a different place inside a common writing (雒陽).
NO_LINK_PLACE = {"長子", "房子", "符節", "分水", "海防", "公安", "同並", "安定", "平原", "當塗", "望海", "三水", "三江",
                 "白水", "南城", "安國", "東光", "臨江", "雒"}
# Single-character places that rarely occur inside other words; other single characters (吳, 代, 宛…) stay unlinked.
ONE_CHAR = set("鄴譙薊郿皖涿郯郪鄂鄃鄞鄨鄳酈鬲黟穰繒圉涅淩羌氐倭")
ERA_AFTER = re.compile(r"[元0-9０-９一二三四五六七八九十]*年|[（(]?[0-9]+")  # 建安十三年, 建安年間: an era, not the place
# A place name followed by one of these is part of something else: 河南省, 河南岸, 鄱陽湖, 華北平原, 東平陵, 東漢安帝
NOT_BEFORE = set("省市區湖岸期原陵帝")
DYNASTY = set("東西後蜀季")  # 東漢中平, 蜀漢中: a 漢- place name right after these is the dynasty


def text_targets(files: dict[str, str], pfiles: dict[str, str]) -> dict[str, str]:
    """Display name -> path: published Sanguo persons, then place and 州 entries."""
    from build_sanguo_entries import link_targets  # noqa: PLC0415
    persons = {f.stem for f in (ROOT / "人物/三國").glob("*.md") if "Your content here" not in f.read_text(encoding="utf-8")}
    targets = link_targets(persons)
    for e, f in [*pfiles.items(), *files.items()]:  # a place page wins over a 州 page of the same name (none but peoples)
        if e not in NO_LINK_PLACE and (len(e) > 1 or e in ONE_CHAR) and e not in targets:
            targets[e] = f"/地點/{f}"
    return targets


def link_intro(text: str, self_name: str, targets: dict[str, str]) -> str:
    """Link each target's first mention; the longest name wins, era names followed by a year stay plain."""
    names = sorted((n for n in targets if n != self_name), key=len, reverse=True)
    pat, seen = re.compile("|".join(map(re.escape, names + [self_name]))), {self_name}

    def sub(m: re.Match) -> str:
        n = m.group(0)
        place = targets.get(n, "").startswith("/地點/")
        if n in seen or place and (ERA_AFTER.match(text, m.end()) or text[m.end():m.end() + 1] in NOT_BEFORE
                                   or n[0] == "漢" and text[m.start() - 1:m.start()] in DYNASTY):
            return n
        seen.add(n)
        return f"[{n}]({targets[n]})"

    return pat.sub(sub, text)


def link(e: str, files: dict[str, str]) -> str:
    f = files.get(e)
    return f"[{e}](/地點/{f})" if f else e


def main() -> None:
    dry = "--dry-run" in sys.argv
    export, rows, provs, facts = load()
    entry_of = {(r["dataset"], int(r["id"])): r["entry"] for r in rows}
    by_entry = defaultdict(list)
    for r in rows:
        if r["entry"]:
            by_entry[r["entry"]].append(r)
    prov_entry = {k: v["entry"] for k, v in provs.items() if v["entry"]}
    shared = {e for e in prov_entry.values() if e in by_entry}  # 州 named like a place (SAN14 peoples)
    prov_entries = set(prov_entry.values())
    files, pfiles = file_names(set(by_entry), prov_entries)
    order = [g[0] for g in GAMES]

    def name_of(ds: str, pid: int) -> str:
        e = entry_of.get((ds, pid))
        p = export[ds].get(pid, {})
        return link(e, files) if e else (p.get("name") or f"{p.get('level', '')} {pid}")

    def owner(ds: str, p: dict) -> str:
        if p.get("province"):
            pe = prov_entry.get((ds, p["province"]))
            return link(pe, pfiles) if pe else p["province"]
        if "parentCity" in p:
            mark = "（推定）" if "parentCity" in p.get("uncertain", []) else ""
            return name_of(ds, p["parentCity"]) + mark
        return "—"

    written = 0
    force = "--force" in sys.argv
    targets = text_targets(files, pfiles)

    def write(path: Path, new_text: str, blocks: dict[str, str]) -> None:
        nonlocal written
        old = path.read_text(encoding="utf-8") if path.exists() else None
        text = new_text if old is None else keep_created(old, new_text) if force else replace_blocks(old, blocks)
        if not path.exists() or text != path.read_text(encoding="utf-8"):
            written += 1
            if not dry:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    # ---- place entries
    for e, erows in by_entry.items():
        per_ds = defaultdict(list)
        for r in erows:
            per_ds[r["dataset"]].append(export[r["dataset"]][int(r["id"])])
        table = ["<details class=\"kw-stats\" open>", "<summary>歷代資料</summary>", "",
                 "| 作品 | 遊戲中的等級 | 所屬 | 相鄰 |", "| :---: | :---: | :---: | :--- |"]
        maps = []
        for ds in order:
            if ds not in per_ds:
                continue
            ps = per_ds[ds]
            levels = "、".join(dict.fromkeys(p["level"].translate(LEVEL_GLYPH) for p in ps))
            main = ps[0]
            adj = "、".join(dict.fromkeys(name_of(ds, a) for p in ps for a in p.get("adjacent", []))) or "—"
            table.append(f"| <kbd>{KBD[ds]}</kbd> | {levels} | {owner(ds, main)} | {adj} |")
            for p in ps:
                for m in p.get("battlemaps", []):
                    maps.append((ds, m))
        table += ["", "</details>"]
        writings = defaultdict(list)
        for r in erows:
            if r["game_name"] != e and r["diff"]:
                writings[(r["game_name"], r["diff"])].append(KBD[r["dataset"]])
        f = facts.get(e, {})
        intro = link_intro(f["intro"], e, targets) if f.get("intro") else "{簡介}"
        write(OUT / "地點" / f"{files[e]}.md", render_place(e, files, erows, table, writings, f, intro, maps, per_ds),
              {"places-main": "\n".join(table)})

    # ---- 州 entries (peoples share their place entry)
    for pe in sorted(prov_entries - {e for e in shared if is_people(e)}):
        lines = ["<details class=\"kw-stats\" open>", "<summary>歷代所轄地點</summary>", "",
                 "| 作品 | 地點 |", "| :---: | :--- |"]
        for ds in order:
            members = [p for p in export[ds].values() if p.get("province") and prov_entry.get((ds, p["province"])) == pe]
            if not members:
                continue
            if ds == "san1-pc98":
                ids = sorted(p["id"] for p in members)
                lines.append(f"| <kbd>{KBD[ds]}</kbd> | 國 {', '.join(map(str, ids))} |")
            else:
                lines.append(f"| <kbd>{KBD[ds]}</kbd> | {'、'.join(dict.fromkeys(name_of(ds, p['id']) for p in members))} |")
        lines += ["", "</details>"]
        writings = defaultdict(list)
        for (ds, g), v in provs.items():
            if v["entry"] == pe and g != pe:
                writings[(g, v["diff"])].append(KBD[ds])
        write(OUT / "地點" / f"{pfiles[pe]}.md", render_province(pe, lines, writings, facts.get(f"州:{pe}") or facts.get(pe, {}), targets),
              {"province-places": "\n".join(lines)})

    # ---- per-game city lists
    for ds, kbd, game, tag in GAMES:
        sections = defaultdict(list)
        for p in export[ds].values():
            sections[p["level"].translate(LEVEL_GLYPH)].append(p)
        out = []
        for level, ps in sections.items():
            out += [f"### {level}", "", "| 編號 | 名稱 | 所屬 | 相鄰 | 備註 |", "| ---: | :--- | :--- | :--- | :--- |"]
            for p in sorted(ps, key=lambda p: p["id"]):
                e = entry_of.get((ds, p["id"]))
                shown = link(e, files) if e else (p.get("name") or "—")
                if e and p.get("name") and p["name"] != e:
                    shown += f"（{p['name']}）"
                note = p["nameBorrowed"]["name"] + "（借自三国志ツクール）" if p.get("nameBorrowed") else ""
                adj = "、".join(name_of(ds, a) for a in p.get("adjacent", [])) or "—"
                out.append(f"| {p['id']} | {shown} | {owner(ds, p)} | {adj} | {note} |")
            out.append("")
        write(OUT / "遊戲" / game / "都市資料一覽.md", render_game(game, tag, export[ds], "\n".join(out).rstrip(),
                                                              facts.get(f"遊戲:{game}", {}).get("summary")),
              {"places-index": "\n".join(out).rstrip()})
    print(f"{'would write' if dry else 'wrote'} {written} files")


def front(title: str, desc: str, tags: str) -> str:
    return (f"---\ntitle: {title}\ndescription: \"{desc}\"\npublished: true\ndate: {NOW}\ntags: {tags}\n"
            f"editor: markdown\ndateCreated: {NOW}\n---")


def writing_row(writings: dict) -> str | None:
    if not writings:
        return None
    parts = [f"{g}（{'、'.join(f'<kbd>{k}</kbd>' for k in dict.fromkeys(ks))}{DIFF_NOTE.get(d, '')}）"
             for (g, d), ks in writings.items()]
    return "| 遊戲寫法 | " + "；".join(parts) + " |"


def basic_rows(f: dict) -> list[str]:
    rows = []
    for key, label in (("han_division", "漢末政區"), ("han_level", "政區等級"), ("han_province", "漢末所屬州"), ("today", "今地")):
        if f.get(key):
            rows.append(f"| {label} | {f[key]} |")
    return rows


def refs(f: dict, e: str) -> list[str]:
    titles = f.get("refs") or [e]
    return [f"- [{t} - 维基百科](https://zh.wikipedia.org/wiki/{t.replace(' ', '_')})" for t in titles]


def event_line(ev: str) -> str:
    """「200 年：官渡之戰」 -> a list item linking the event entry."""
    year, _, name = ev.partition("：")
    return f"- {year}：[{name}](/事件/{name})" if name else f"- {ev}"


def suikoden_see_also(page: str) -> list[str]:
    """A hatnote to the same-named Suikoden 州 (地點/<name>_水滸), on the page that holds the bare name."""
    from build_suikoden_places import entries  # imports this module; import lazily
    global _SUIKODEN
    if "_SUIKODEN" not in globals():
        _SUIKODEN = {p["entry"] for p in entries() if p["sanguo"]}
    return [f"> 水滸傳・天命之誓的同名州見 [{page} (水滸)](/地點/{page}_水滸)。"] if page in _SUIKODEN else []


def render_place(e, files, erows, table, writings, f, intro, maps, per_ds) -> str:
    desc = f.get("description") or f"三國志系列的地點：{e}"
    parts = [front(files[e].replace("_", " (", 1) + ")" if "_" in files[e] else e, desc, "三國, 地點"),
             *suikoden_see_also(files[e]),
             "## 基本資料\n\n| 項目 | 內容 |\n| :--- | :--- |\n" + "\n".join([f"| 名稱 | {e} |", *basic_rows(f), *filter(None, [writing_row(writings)])]),
             "## 遊戲中的地點資料\n\n" + block("places-main", "\n".join(table)),
             "## 簡介\n\n" + intro]
    if f.get("events"):
        parts.append("## 發生於此的事件\n\n" + "\n".join(event_line(ev) for ev in f["events"]))
    parts.append("## References\n\n" + "\n".join(refs(f, e)))
    return "\n\n".join(parts) + "\n"


def render_province(pe, lines, writings, f, targets) -> str:
    rows = [f"| 名稱 | {pe} |"]
    if f.get("han_division"):
        rows.append(f"| 漢末治所 | {f['han_division']} |")
    w = writing_row(writings)
    if w:
        rows.append(w)
    parts = [front(pe, f.get("description") or f"三國志系列中的州：{pe}", "三國, 地點, 州"),
             *suikoden_see_also(pe),
             "## 基本資料\n\n| 項目 | 內容 |\n| :--- | :--- |\n" + "\n".join(rows),
             "## 各代所轄地點\n\n" + block("province-places", "\n".join(lines)),
             "## 簡介\n\n" + (link_intro(f["intro"], pe, targets) if f.get("intro") else "{簡介}"),
             "## References\n\n" + "\n".join(refs(f, pe))]
    return "\n\n".join(parts) + "\n"


def render_game(game, tag, places, index, summary) -> str:
    parts = [front(f"{game} 都市資料一覽", f"{game}的全部地點一覽", f"三國, {tag}, 地點"),
             "## 概要\n\n" + (summary or "{概要}"),
             "## 地點一覽\n\n" + block("places-index", index),
             "## 資料來源\n\n- kaodata-re 匯出（koei-places/1）"]
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    main()
