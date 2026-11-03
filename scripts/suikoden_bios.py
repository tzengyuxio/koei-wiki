#!/usr/bin/env python3
"""Draft Suikoden bios with hikari's Qwen, grounded in the 120-chapter novel text.

For each person: pick the novel chapters that mention them most (up to a char
budget), add the zh.wikipedia plain-text extract, and ask Qwen to summarise.
Qwen must only use the supplied sources; output is plain prose (links are
added later by a separate pass).

Usage: scripts/suikoden_bios.py 宋江 林沖 時遷 [--thinking] [--out FILE]
Output: assets/data/suikoden/suikoden-bios.jsonl (one JSON per person; re-running
        a name replaces its line)
Key:    Keychain service hikari-litellm-koei-wiki
Env:    KOEI_LLM_API and KOEI_LLM_KEY_FILE override the endpoint and key (for running
        on the model host itself, e.g. in tmux, without the Keychain)
"""

import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "assets/data/suikoden/suikoden-persons-mapping.csv"
OUT = ROOT / "assets/data/suikoden/suikoden-bios.jsonl"
CACHE = Path.home() / ".cache/koei-wiki/suikoden"
API = os.environ.get("KOEI_LLM_API", "https://hikari.tail81eb54.ts.net:4000/v1/chat/completions")
# Wikimedia asks for a descriptive User-Agent; never put personal contact info here.
UA = {"User-Agent": "koei-wiki-bios/1 (https://github.com/tzengyuxio/koei-wiki)"}
NOVEL_TITLE = "水滸傳 (120回本)/第{:03d}回"
DEADLINE = 1200  # seconds per request; the slowest normal one so far took ~300s
NOVEL_BUDGET = 80000  # chars of novel text per person (~60k tokens, half of the 131k context)
# Extra search keys for people the novel never names in full (e.g. 「姓寇名烕」).
NOVEL_KEYS = {"寇烕": ["名烕"], "何玄通": ["法諱玄通"], "梁世傑": ["梁中書"]}

SYSTEM = """你是《水滸傳》百科的編輯，替人物條目撰寫「列傳」。
規則：
1. 只能根據使用者提供的資料寫作，資料沒有的事不要寫，不要憑記憶補充。資料之間矛盾時以小說原文為準。
   「全書回目」只用來掌握情節先後；某段情節若只出現在回目、沒有對應的小說原文，就只能概括一句或直接略過，不要補寫細節（人數、金額、對話、地名等）。
   人物的功勞、遭遇要看清楚原文是誰做的，不要張冠李戴；不同戰役（征遼、征田虎、征王慶、征方臘）的情節不要混在一起。
2. 依《水滸傳》（一百二十回本）的小說情節敘述此人的生平：出身、上梁山的經過、重要事蹟、結局。
3. 使用臺灣繁體中文與全形標點，自然分段，不加任何標題、清單、連結或 Markdown 記號。
4. 不要評論遊戲，不要寫「本條目」「綜上所述」之類的套話，不要誇大或抒情。
5. 字數：{length}。"""


def get_json(url: str) -> dict:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(int(e.headers.get("Retry-After", 0) or 0) or 10 * (attempt + 1))


def strip_wikitext(text: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", text, flags=re.S)
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>|'''?", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_novel() -> tuple[list[str], list[str]]:
    """Return (chapter titles, chapter texts) for chapters 1-120."""
    path = CACHE / "novel-120-v2.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["titles"], data["texts"]
    chapters, titles = {}, {}
    for start in range(1, 121, 40):
        batch = "|".join(NOVEL_TITLE.format(i) for i in range(start, min(start + 40, 121)))
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": 2, "prop": "revisions",
            "rvprop": "content", "rvslots": "main", "titles": batch,
        })
        for page in get_json(f"https://zh.wikisource.org/w/api.php?{q}")["query"]["pages"]:
            n = int(page["title"].rsplit("第", 1)[1].rstrip("回"))
            raw = page["revisions"][0]["slots"]["main"]["content"]
            m = re.search(r"\{\{Novel\|[^|]*\|([^|}]*)", raw)
            titles[n] = m.group(1).strip() if m else f"第{n}回"
            chapters[n] = strip_wikitext(raw)
        time.sleep(1)
    data = {"titles": [titles[i] for i in range(1, 121)], "texts": [chapters[i] for i in range(1, 121)]}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data["titles"], data["texts"]


def wiki_extract(name: str) -> tuple[str, str]:
    path = CACHE / "wiki" / f"{name}.json"
    if path.exists():
        return tuple(json.loads(path.read_text(encoding="utf-8")))
    found = _wiki_extract(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    return found


def _wiki_extract(name: str) -> tuple[str, str]:
    for title in (f"{name} (水滸傳)", name):
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": 2, "prop": "extracts",
            "explaintext": 1, "redirects": 1, "titles": title, "variant": "zh-tw",
        })
        page = get_json(f"https://zh.wikipedia.org/w/api.php?{q}")["query"]["pages"][0]
        text = page.get("extract", "")
        if text and ("水滸" in text or "水浒" in text):
            return page["title"], text[:15000]
    return "", ""


def pick_chapters(novel: list[str], keys: list[str]) -> list[int]:
    """First and last chapters mentioning the person, then the most-mentioning ones."""
    score = [(sum(ch.count(k) for k in keys), i) for i, ch in enumerate(novel)]
    hits = [i for s, i in score if s]
    if not hits:
        return []
    order = [hits[0], hits[-1]] + [i for s, i in sorted(score, reverse=True) if s]
    picked, used = [], 0
    for i in order:
        if i in picked or used + len(novel[i]) > NOVEL_BUDGET:
            continue
        picked.append(i)
        used += len(novel[i])
    return sorted(picked)


def length_for(row: dict) -> str:
    if row["天罡地煞"] == "天罡":
        return "約 600–1000 字，核心人物（如宋江）可至 1200 字"
    if row["天罡地煞"] == "地煞":
        return "約 300–600 字"
    return "約 300 字；資料少就如實簡短"


def ask_qwen(system: str, user: str, thinking: bool, max_tokens: int = 28000) -> tuple[str, dict]:
    key_file = os.environ.get("KOEI_LLM_KEY_FILE")
    key = Path(key_file).read_text().strip() if key_file else subprocess.run(
        ["security", "find-generic-password", "-s", "hikari-litellm-koei-wiki", "-a",
         subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip(), "-w"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    body = {
        "model": "qwen-tw",
        "max_tokens": max_tokens if thinking else 3000,  # thinking shares this budget
        "chat_template_kwargs": {"enable_thinking": thinking},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    # Hard deadline: the proxy sometimes keeps the connection open after the model has
    # dropped the request, so the socket timeout never fires.
    def give_up(*_):
        raise TimeoutError(f"no response in {DEADLINE}s")

    signal.signal(signal.SIGALRM, give_up)
    signal.alarm(DEADLINE)
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            res = json.load(r)
    finally:
        signal.alarm(0)
    text = res["choices"][0]["message"]["content"]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return text, res.get("usage", {})


def main() -> None:
    thinking = "--thinking" in sys.argv
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT
    args = [a for i, a in enumerate(sys.argv[1:], 1) if sys.argv[i - 1] != "--out"]
    names = [a for a in args if not a.startswith("--")]
    rows = {r["姓名"]: r for r in csv.DictReader(open(MAPPING, encoding="utf-8"))}
    titles, novel = load_novel()
    toc = "\n".join(titles)
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done[rec["name"]] = rec

    for name in names:
        row = rows[name]
        keys = [name] + ([row["綽號"]] if row["綽號"] else []) + NOVEL_KEYS.get(name, [])
        chapters = pick_chapters(novel, keys)
        wiki_title, wiki_text = wiki_extract(name)
        facts = f"姓名：{name}\n綽號：{row['綽號'] or '無'}\n星號：{row['星號'] or '非一百零八星'}\n梁山座次：{row['梁山座次'] or '無'}"
        parts = [f"【基本資料】\n{facts}", f"【全書回目】\n{toc}"]
        if wiki_text:
            parts.append(f"【維基百科：{wiki_title}】\n{wiki_text}")
        for i in chapters:
            parts.append(f"【小說原文 第{i + 1}回】\n{novel[i]}")
        user = "\n\n".join(parts) + f"\n\n請根據以上資料，撰寫{name}的列傳。"
        t0 = time.time()
        bio, usage = ask_qwen(SYSTEM.format(length=length_for(row)), user, thinking)
        print(f"{name}: {time.time() - t0:.0f}s, chapters {[i + 1 for i in chapters]}, "
              f"{len(bio)} chars, usage {usage}", flush=True)
        done[name] = {
            "name": name,
            "bio": bio,
            "sources": {
                "novel_chapters": [i + 1 for i in chapters],
                "wikipedia": wiki_title,
            },
            "model": "qwen-tw" + (" thinking" if thinking else ""),
        }
        out.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
