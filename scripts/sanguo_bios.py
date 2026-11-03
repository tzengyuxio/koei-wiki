#!/usr/bin/env python3
"""Draft Sanguo bios with hikari's Qwen, grounded in KOEI's in-game biographies.

Sources per person, in order of weight:
  1. In-game bios from five games (kaodata-re export, not in git):
     三國志IV・V・VI 威力加強版 (one paragraph each) and 三國志13・14 威力加強版
     (簡介 + 演義 + 史實 segments). Segments starting with 無記述 are dropped.
  2. zh.wikipedia plain-text extract (cached).
  3. The earlier Gemini draft in sanguo-bios.jsonl, as a cross-check only.

Qwen writes two parts: 列傳 (EDITORIAL §4; first sentence states the source:
正史 / 演義 / other) and 演義中的形象 (only when 演義 differs a lot from 正史).
Output is plain prose; links are added when entries are built.

Usage: scripts/sanguo_bios.py [--all | 名1 名2 ...] [--thinking] [--out FILE]
  --all  everyone in persons-mapping.csv with in-game bios from at least two games
         (people with only one are kept for later), skipping names already in the output
Output: assets/data/sanguo/sanguo-bios-qwen.jsonl (one JSON per person; re-running
        a name replaces its line)
Key:    Keychain service hikari-litellm-koei-wiki (KOEI_LLM_API / KOEI_LLM_KEY_FILE override,
        see suikoden_bios.py); KAODATA_EXPORT overrides the export directory
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suikoden_bios import ask_qwen, get_json  # noqa: E402  (same endpoint and HTTP helper)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets/data/sanguo"
OUT = DATA / "sanguo-bios-qwen.jsonl"
# kaodata-re export, not in git
EXPORT = Path(os.environ.get("KAODATA_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki"))
CACHE = Path.home() / ".cache/koei-wiki/sanguo/wiki"
# mapping column -> (export file, game title). PC-98 and DOS share character IDs.
GAMES = [
    ("san4pk-pc98", "san4pk-dos", "三國志IV 威力加強版"),
    ("san5pk-pc98", "san5pk-dos", "三國志V 威力加強版"),
    ("san6pk-win", "san6pk-win", "三國志VI 威力加強版"),
    ("san13pk-win", "san13pk-win", "三國志13 威力加強版"),
    ("san14pk-win", "san14pk-win", "三國志14 威力加強版"),
]
MAINLINE_COLS = [c for c in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8")).fieldnames
                 if c.startswith("san") and c.endswith(("-pc98", "-win")) and c != "eiketsu-pc98"]

SYSTEM = """你是三國人物百科的編輯，替人物條目撰寫「列傳」與「演義中的形象」。
資料說明：
- 【遊戲列傳】是光榮《三國志》系列遊戲內的人物介紹。IV、V、VI 只有一段，常把《三國演義》情節和正史混在一起；13、14 分成「簡介」「演義」「史實」三段，「史實」指正史記載。
- 【維基百科】主要依正史。【舊稿】是另一個模型先前寫的草稿，可能有錯，只能拿來對照，不能當成依據。
規則：
1. 只能根據提供的資料寫作，資料沒有的事不要寫，不要憑記憶補充。正史事蹟以「史實」段與維基百科為準；演義情節以「演義」段為準。分不清是正史還是演義的情節，寧可不寫。
2. 先判斷此人的出典：正史有記載的人物，「列傳」寫正史生平；只見於《三國演義》的虛構人物（如周倉），「列傳」寫演義情節；演義以外的虛構人物（如出自《花關索傳》的鮑三娘），寫出處故事。「列傳」第一句要交代出典，例如「〇〇，字〇〇，〇〇人，東漢末年〇〇的將領。」或「〇〇是《三國演義》虛構的人物，……」。
3. 「演義中的形象」只在此人是正史人物、而且演義的描寫和正史差異大時才寫（例如演義虛構了重要情節、改了死法、誇大或貶低其形象），寫明演義怎麼寫、與正史哪裡不同；差異不大，或此人本身就是虛構人物，就只寫「無」。
4. 不要提到遊戲、能力值或光榮，不要寫「本條目」「綜上所述」之類的套話，不要誇大或抒情。
5. 使用臺灣繁體中文與全形標點，自然分段，不加標題、清單、連結或 Markdown 記號。
6. 字數：「列傳」{length}；「演義中的形象」約 100–300 字。字數是上限，不是目標：資料少就寫短，不要換句話重述前文，也不要加「可見」「顯示」「說明」之類解讀前一句的句子來湊字數。
輸出格式（照抄兩個標記，標記外不要有其他文字）：
【列傳】
（內容）
【演義中的形象】
（內容或「無」）"""


def first_ids(cell: str) -> list[int]:
    return [int(x) for x in cell.split("|")] if cell else []


def load_game_bios() -> dict[str, dict[int, list[tuple[str, str]]]]:
    """export file -> id -> [(kind, text)] with 無記述 segments dropped."""
    out = {}
    for _, export, _ in GAMES:
        segs: dict[int, list] = {}
        for line in open(EXPORT / f"{export}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r["text"].strip() and not r["text"].startswith("無記述"):
                segs.setdefault(r["id"], []).append((r["kind"], r["text"].strip()))
        out[export] = segs
    return out


def game_parts(row: dict, bios: dict) -> tuple[list[str], list[str]]:
    parts, used = [], []
    for col, export, title in GAMES:
        segs = [s for i in first_ids(row[col]) for s in bios[export].get(i, [])]
        if not segs:
            continue
        used.append(export)
        body = "\n".join(text if kind == "單段" else f"〈{kind}〉{text}" for kind, text in segs)
        parts.append(f"【遊戲列傳：{title}】\n{body}")
    return parts, used


def wiki_extract(wiki: str, title_hint: str) -> tuple[str, str]:
    path = CACHE / f"{wiki}.json"
    if path.exists():
        return tuple(json.loads(path.read_text(encoding="utf-8")))
    base, _, tag = wiki.partition("_")
    found = ("", "")
    for title in [t for t in (title_hint, f"{base} ({tag})" if tag else "", base) if t]:
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": 2, "prop": "extracts",
            "explaintext": 1, "redirects": 1, "titles": title, "variant": "zh-tw",
        })
        page = get_json(f"https://zh.wikipedia.org/w/api.php?{q}")["query"]["pages"][0]
        text = page.get("extract", "")
        is_disambig = re.search("可以指|可能指|可指", text[:300])
        if text and not is_disambig and re.search("三國|三国|東漢|东汉|演義|演义", text):
            found = (page["title"], text[:15000])
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    return found


def length_for(row: dict) -> str:
    n = sum(1 for c in MAINLINE_COLS if row[c])
    if n == 14:
        return "約 600–1000 字，核心人物（如劉備、曹操、諸葛亮）可至 1200 字"
    if n >= 8:
        return "約 400–600 字"
    return "約 300 字；資料少就如實簡短"


def split_output(text: str) -> tuple[str, str]:
    m = re.search(r"【列傳】\s*(.*?)\s*【演義中的形象】\s*(.*)", text, re.S)
    if not m:
        return text.strip(), ""
    bio, yanyi = m.group(1).strip(), m.group(2).strip()
    return bio, "" if yanyi.strip("「」。 ") == "無" else yanyi


def main() -> None:
    thinking = "--thinking" in sys.argv
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT
    args = [a for i, a in enumerate(sys.argv[1:], 1) if sys.argv[i - 1] != "--out"]
    rows = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8"))}
    old = {(r := json.loads(line))["name"]: r
           for line in open(DATA / "sanguo-bios.jsonl", encoding="utf-8") if line.strip()}
    new = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-new.csv", encoding="utf-8"))}
    bios = load_game_bios()
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done[rec["name"]] = rec
    if "--all" in sys.argv:
        names = [n for n in rows if n not in done and len(game_parts(rows[n], bios)[1]) >= 2]
    else:
        names = [a for a in args if not a.startswith("--")]

    for wiki in names:
        row = rows[wiki]
        name = wiki.partition("_")[0]
        parts, used = game_parts(row, bios)
        prev = old.get(wiki, {})
        hint = ""
        if prev.get("refs"):
            hint = urllib.parse.unquote(prev["refs"][0].rsplit("/wiki/", 1)[-1]).replace("_", " ")
        wiki_title, wiki_text = wiki_extract(wiki, hint)
        facts = [f"姓名：{name}"]
        if prev.get("courtesy"):
            facts.append(f"字：{prev['courtesy']}")
        if (faction := prev.get("faction") or new.get(wiki, {}).get("勢力") or row["勢力"]):
            facts.append(f"所屬：{faction}")
        if wiki != name:
            facts.append(f"區分：同名者中的「{wiki.partition('_')[2]}」那一位")
        ctx = ["【基本資料】\n" + "\n".join(facts)] + parts
        if wiki_text:
            ctx.append(f"【維基百科：{wiki_title}】\n{wiki_text}")
        if prev.get("bio"):
            ctx.append("【舊稿】\n" + re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", prev["bio"]))
        user = "\n\n".join(ctx) + f"\n\n請根據以上資料，撰寫{name}的列傳與演義中的形象。"
        t0 = time.time()
        try:
            text, usage = ask_qwen(SYSTEM.format(length=length_for(row)), user, thinking, max_tokens=48000)
        except Exception as e:  # keep the batch going; the name is retried on the next --all
            print(f"FAILED {wiki}: {e}", flush=True)
            continue
        bio, yanyi = split_output(text)
        print(f"{wiki}: {time.time() - t0:.0f}s, games {used}, wiki {bool(wiki_text)}, "
              f"{len(bio)}+{len(yanyi)} chars, tokens {usage.get('completion_tokens')}", flush=True)
        done[wiki] = {
            "name": wiki,
            "bio": bio,
            "yanyi": yanyi,
            "sources": {"games": used, "wikipedia": wiki_title},
            "model": "qwen-tw" + (" thinking" if thinking else ""),
        }
        out.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
