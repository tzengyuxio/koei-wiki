#!/usr/bin/env python3
"""Write Nobunaga person bios (列傳) with Claude through the claude CLI (subscription quota).

Design: docs/backlog/nobunaga-persons.mkdn step 5; same workflow as scripts/sanguo_bios_claude.py.
Sources per person: the in-game bios of every generation (kaodata-re export/koei-wiki/<dataset>.jsonl,
Japanese except 信7 in Chinese), the ja.wikipedia article (plain text, cached), and facts from the game
data with the wiki's spelling of related people, so the bio uses the entry names.

Usage:
  python3 scripts/nobunaga_bios.py local 名 ... [--jobs N] [--model M] [--redo]   # skips names already written by M unless --redo
  .venv/bin/python scripts/nobunaga_bios.py submit [名 ... | --next N] [--model M]  # Message Batches (half price)
  .venv/bin/python scripts/nobunaga_bios.py collect <batch id>         # save results, trim overshoots, print cost
  python3 scripts/nobunaga_bios.py show 名                               # print the prompt only
submit/collect need the anthropic package (.venv) and ANTHROPIC_API_KEY, from Keychain service anthropic-simagame:
  env ANTHROPIC_API_KEY=$(security find-generic-password -s anthropic-simagame -a "$USER" -w) .venv/bin/python ...
--next N takes the next N first-batch people without a bio, most generations first.
Output: assets/data/nobunaga/nobunaga-bios.jsonl (re-running a name replaces its line)
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_nobunaga_entries import (  # noqa: E402
    DATA, GAMES, ja_name, load_persons, main_lords, person_title, records)
from build_nobunaga_mapping import DATASETS, to_tw  # noqa: E402

EXPORT = Path(os.environ.get("KOEI_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki"))
OUT = DATA / "nobunaga-bios.jsonl"
CACHE = Path.home() / ".cache/koei-wiki/nobunaga-jawiki-text"
MODEL = "claude-opus-5-5"
BATCHES = Path.home() / ".cache/koei-wiki/nobunaga-batches"  # custom_id -> name and sources, per batch
PRICE = {"claude-opus-5-5": (4.0, 20.0)}  # USD per MTok (input, output); batches are half
WIKI_CHARS = 30000
RELATIONS = {"father": "父", "mother": "母", "spouse": "配偶", "sworn": "義兄弟", "siblings": "兄弟姊妹",
             "children": "子女"}

SYSTEM = """你是日本戰國人物百科的編輯，替人物條目寫「列傳」（人物生平）。

資料說明：
- 【遊戲列傳】是光榮《信長之野望》各代的人物介紹（多為日文，信7 為中文），篇幅短，常混入俗說、軍記物語或小說的情節。
- 【日文維基百科】是此人的日文維基條目（可能截斷），以史實為主，也會整理俗說與異說。可能是同名的別人，要對照生卒與事蹟判斷；對不上就不要用。
- 【遊戲資料】是遊戲裡的生卒年、主君與親屬，數值由遊戲設定，不一定是史實。後面附上本百科的人名寫法。

規則：
1. 事蹟以【日文維基百科】為準；只見於遊戲列傳的事，確定是通行的說法才寫，並寫成「相傳」「據《某書》記載」。資料都沒有的事不要寫；你自己的知識只用來讀懂資料，不用來補充事蹟。日文維基標明是俗說、創作或有疑問的，不要當成史實。
2. 第一句交代此人是誰，例如「北條氏康是戰國時代相模國的大名，後北條氏第三代當主。」不用寫讀音和日文寫法。
3. 紀年：第一次提到某年寫「和曆年號＋年（西元年）」，例如「永祿三年（1560年）」；之後同一年號可省略西元。年號與西元要對得上。
4. 人名、地名用繁體字的漢字寫法（北條、齋藤、尾張國、小田原城），【遊戲資料】列出的人一律照所附的本百科寫法。日文的官職、身分、制度用中文讀者看得懂的說法：「當主」「家督」「元服」「守護」「國人」可以用；假名要改寫成漢字或意譯，不要留下日文假名；和歌、辭世不引用原文。不用日文直譯詞（離反、討伐隊、出奔先、武將登用、仕奉等）。
5. 只寫此人：背景用一句交代，不展開父兄、主君或對手的事蹟。不要同義重複，不要寫「可見」「顯示」之類解讀前一句的句子，不要誇大或抒情，不要寫「本條目」「綜上所述」。不要談資料本身：不寫「據維基百科」「生卒年不詳」「此後不見記載」「關於此人有諸說」；結局不明就不寫結局。不寫史學討論：不寫「近年的研究」「通說」「一說」「異說」，不並列不同說法，說法不一時只寫日文維基採用的那一種；也不寫後世的評價、傳說形象和小說、戲劇裡的形象。
6. 不要提到遊戲、能力值或光榮。使用臺灣繁體中文與全形標點，自然分段，不加標題、清單、連結或 Markdown 記號。
7. 字數：約 {target} 字，最多 {cap} 字（標點也算）；資料少就寫短。字數是硬上限，寧短勿長：挑此人最重要的幾件事寫，核心人物也只挑五、六件大事；合戰細節、官位遷轉、旁人言論只留最關鍵的。不用背景或旁人的事湊字數。

以 JSON 回答：bio 是列傳。"""

SCHEMA = {
    "type": "object",
    "properties": {"bio": {"type": "string"}},
    "required": ["bio"],
    "additionalProperties": False,
}


CORE = {"織田信長", "豐臣秀吉", "德川家康", "武田信玄", "上杉謙信"}
SHORTEN = """把下面的列傳刪到 {cap} 字以內（標點也算）。只刪句子或子句，必要時合併句子；不新增事實，不改人名、年代和用詞；保留原本的分段（段與段之間空一行）。以 JSON 回答：bio 是刪減後的列傳。"""


def max_length(wiki: str, row: dict) -> int:
    gens = int(row["代數"])
    if wiki in CORE:
        return 900
    return 600 if gens >= 11 else 400 if gens >= 8 else 250


def wiki_text(title: str) -> str:
    """Plain text of a ja.wikipedia article, cached; '' when there is none."""
    path = CACHE / f"{title.replace('/', '_')}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "titles": title,
                                "redirects": 1, "format": "json"})
    req = urllib.request.Request("https://ja.wikipedia.org/w/api.php?" + q, headers={"User-Agent": "koei-wiki-build"})
    for wait in (1, 5, 15, 30, 60):
        time.sleep(wait)
        try:
            pages = json.load(urllib.request.urlopen(req, timeout=30))["query"]["pages"]
            break
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    else:
        raise RuntimeError(f"ja.wikipedia keeps answering 429 for {title}")
    text = next(iter(pages.values())).get("extract", "")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def life_part(text: str) -> str:
    """The lead plus the sections up to and including 生涯 (人物, 逸話, 登場作品 … are left out)."""
    parts = re.split(r"(?m)^(?===[^=])", text)
    keep, seen_life = [parts[0]], False
    for part in parts[1:]:
        title = part.split("\n", 1)[0].strip("= ")
        if seen_life and title not in ("没後", "死後", "経歴"):
            break
        keep.append(part)
        seen_life = seen_life or "生涯" in title
    return "".join(keep) if seen_life else text


def load_inputs():
    mapping = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8"))}
    persons = load_persons()
    bios = {}
    for ds in DATASETS:
        path = EXPORT / f"{ds}.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    b = json.loads(line)
                    bios.setdefault(ds, {}).setdefault(b["id"], []).append(b["text"])
    owner = {(ds, int(i)): w for w, r in mapping.items() for ds in DATASETS for i in r[ds].split("|") if i}
    names = sorted({n for d in persons.values() for p in d.values() for n in (p["name"], p.get("nameJa")) if n})
    tw = dict(zip(names, to_tw(names)))
    return mapping, persons, bios, owner, tw


def params(wiki: str, inputs) -> tuple[str, str, dict]:
    mapping, persons, bios, owner, tw = inputs
    row, name = mapping[wiki], wiki.partition("_")[0]
    recs = records(row, persons)
    ja = ja_name(name, recs, tw)
    ctx, used, same = [], [], {}  # identical texts (信9–信13 often repeat) are given once
    for ds, r in recs.items():
        for text in bios.get(ds, {}).get(r["id"], []):
            same.setdefault(text, []).append(GAMES[ds][0])
            used.append(ds)
    ctx += [f"【遊戲列傳 {'、'.join(gens)}】\n{text}" for text, gens in same.items()]
    title = person_title(wiki, ja, recs)
    if title and (text := wiki_text(title)):
        text = life_part(text)
        cut = text[:WIKI_CHARS] + ("……（以下截斷）" if len(text) > WIKI_CHARS else "")
        ctx.append(f"【日文維基百科：{title}】\n{cut}")
    facts = [f"條目名：{name}（日文：{ja}）"]
    born = next((r["born"] for r in reversed(list(recs.values())) if r.get("born")), None)
    died = next((r["died"] for r in reversed(list(recs.values())) if r.get("died")), None)
    if born or died:
        facts.append(f"生卒（遊戲設定）：{born or '不詳'}–{died or '不詳'}")
    if lords := main_lords(recs, owner):
        facts.append("主君：" + " → ".join(lords))
    ds = next((d for d in reversed(list(recs)) if recs[d].get("relations", {}).keys() - {"clan"}), None)
    if ds:
        for key, label in RELATIONS.items():
            who = [owner[(ds, i)].partition("_")[0] for i in recs[ds]["relations"].get(key, []) if (ds, i) in owner]
            if who:
                facts.append(f"{label}：" + "、".join(who))
    ctx.append("【遊戲資料】\n" + "\n".join(facts))
    user = "\n\n".join(ctx) + f"\n\n請依以上資料寫{name}的列傳。"
    cap = max_length(wiki, row)
    return SYSTEM.format(target=cap * 4 // 5, cap=cap), user, {"games": used, "jawiki": title, "cap": cap}


def claude(system: str, user: str, model: str, wiki: str) -> tuple[str, dict]:
    cmd = ["claude", "-p", "--model", model, "--effort", "medium", "--tools", "", "--system-prompt", system,
           "--json-schema", json.dumps(SCHEMA, ensure_ascii=False), "--output-format", "json",
           "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"]
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # keep it on the subscription
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(cmd, input=user, capture_output=True, text=True, env=env, cwd=CACHE.parent, timeout=900)
    res = json.loads(out.stdout)
    if res.get("is_error") or not res.get("structured_output"):
        raise RuntimeError(f"{wiki}: {res.get('subtype')} {str(res.get('result'))[:200]}")
    u = res.get("usage", {})
    return res["structured_output"]["bio"].strip(), {
        "input": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
        "output": u.get("output_tokens", 0)}


def local(wiki: str, inputs, model: str) -> dict:
    system, user, sources = params(wiki, inputs)
    bio, usage = claude(system, user, model, wiki)
    if len(bio) > sources["cap"]:  # the model overshoots the limit by 5–15%; a short second call trims it
        sources["draft_chars"] = len(bio)
        bio, more = claude(SHORTEN.format(cap=sources["cap"] * 9 // 10), bio, model, wiki)
        usage = {k: usage[k] + more[k] for k in usage}
    return {"name": wiki, "bio": bio, "sources": sources, "model": model, "usage": usage}


def api_params(system: str, user: str, model: str) -> dict:
    return {"model": model, "max_tokens": 16000, "system": system, "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}}


def api_bio(message, wiki: str) -> tuple[str, dict]:
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"{wiki}: stop_reason {message.stop_reason}")
    bio = json.loads(next(b.text for b in message.content if b.type == "text"))["bio"].strip()
    return bio, {"input": message.usage.input_tokens, "output": message.usage.output_tokens}


def cost(usage: dict, model: str, batch: bool) -> float:
    i, o = PRICE[model]
    return (usage["input"] * i + usage["output"] * o) / 1e6 * (0.5 if batch else 1)


def submit(names: list[str], inputs, model: str) -> None:
    import anthropic
    requests, sources = [], {}
    for i, wiki in enumerate(names):
        system, user, src = params(wiki, inputs)
        requests.append({"custom_id": f"p{i}", "params": api_params(system, user, model)})
        sources[f"p{i}"] = {"name": wiki, "sources": src}
    batch = anthropic.Anthropic().messages.batches.create(requests=requests)
    BATCHES.mkdir(parents=True, exist_ok=True)
    (BATCHES / f"{batch.id}.json").write_text(json.dumps(sources, ensure_ascii=False), encoding="utf-8")
    print(f"submitted {len(requests)} as {batch.id}")


def collect(batch_id: str, model: str) -> None:
    import anthropic
    client = anthropic.Anthropic()
    status = client.messages.batches.retrieve(batch_id)
    if status.processing_status != "ended":
        print(f"{batch_id}: {status.processing_status} {status.request_counts}")
        return
    sources = json.loads((BATCHES / f"{batch_id}.json").read_text(encoding="utf-8"))
    records, spent, trims = [], 0.0, 0
    for result in client.messages.batches.results(batch_id):
        wiki, src = sources[result.custom_id]["name"], sources[result.custom_id]["sources"]
        if result.result.type != "succeeded":
            print(f"FAILED {wiki}: {result.result.type}")
            continue
        try:
            bio, usage = api_bio(result.result.message, wiki)
            spent += cost(usage, model, batch=True)
            if len(bio) > src["cap"]:  # trim overshoots right away with a direct call (full price, small)
                src["draft_chars"], trims = len(bio), trims + 1
                msg = client.messages.create(**api_params(SHORTEN.format(cap=src["cap"] * 9 // 10), bio, model))
                bio, more = api_bio(msg, wiki)
                spent += cost(more, model, batch=False)
                usage = {k: usage[k] + more[k] for k in usage}
        except Exception as e:  # noqa: BLE001  keep the rest; failed names are resubmitted
            print(f"FAILED {wiki}: {e}")
            continue
        records.append({"name": wiki, "bio": bio, "sources": src, "model": model, "batch": batch_id, "usage": usage})
    save(records)
    tin, tout = sum(r["usage"]["input"] for r in records), sum(r["usage"]["output"] for r in records)
    print(f"saved {len(records)}, trimmed {trims}; tokens in {tin} out {tout}; "
          f"about ${spent:.2f} (${spent / max(len(records), 1):.3f} per person)")


# Japanese shinjitai the model sometimes copies from the ja.wikipedia text -> Taiwan standard forms
SHINJITAI = str.maketrans("亀頼郷徳浜塩斎豊沢戸恵竜桜関帰図県鉄広弐粛覇曽栄衆芸恒巻勅浅荘禄浄軽譲狭縄薬煕",
                           "龜賴鄉德濱鹽齋豐澤戶惠龍櫻關歸圖縣鐵廣貳肅霸曾榮眾藝恆卷敕淺莊祿淨輕讓狹繩藥熙")


def tidy(bio: str) -> str:
    """Taiwan character forms, 、 for the Japanese ・ (· in Western names), and a blank line between paragraphs."""
    bio = bio.translate(SHINJITAI)
    bio = re.sub(r"(?<=[\u4e00-\u9fff])・(?=[\u4e00-\u9fff])", "、", bio).replace("・", "·")
    return re.sub(r"\n+", "\n\n", bio.strip())


def save(records: list[dict]) -> None:
    done = {}
    if OUT.exists():
        done = {(r := json.loads(line))["name"]: r for line in OUT.read_text(encoding="utf-8").splitlines() if line}
    done.update({r["name"]: {**r, "bio": tidy(r["bio"])} for r in records})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8")


def main() -> None:
    cmd, args = sys.argv[1], sys.argv[2:]
    model = args[args.index("--model") + 1] if "--model" in args else MODEL
    jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 4
    names = [a for i, a in enumerate(args) if not a.startswith("--") and args[i - 1] not in ("--model", "--jobs", "--next")]
    if cmd == "collect":
        collect(names[0], model)
        return
    inputs = load_inputs()
    if cmd == "show":
        system, user, _ = params(names[0], inputs)
        print(system + "\n\n=====\n\n" + user)
        return
    done = set()
    if OUT.exists() and "--redo" not in args:  # resume: skip what this model already wrote
        done = {r["name"] for line in OUT.read_text(encoding="utf-8").splitlines() if line
                and (r := json.loads(line))["model"] == model}
    if "--next" in args:
        first = [w for w, r in inputs[0].items() if r["第一批"] and w not in done]
        names = sorted(first, key=lambda w: -int(inputs[0][w]["代數"]))[:int(args[args.index("--next") + 1])]
    names = [n for n in names if n not in done]
    for n in names:  # fetch wiki texts one by one first; parallel fetches get 429
        params(n, inputs)
    print(f"{len(names)} to do", flush=True)
    if cmd == "submit":
        submit(names, inputs, model)
        return
    with ThreadPoolExecutor(jobs) as pool:
        for wiki, fut in [(w, pool.submit(local, w, inputs, model)) for w in names]:
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001  keep going; a re-run retries the failures
                print(f"FAILED {wiki}: {e}", flush=True)
                continue
            save([r])
            print(f"{r['name']}: {len(r['bio'])} chars, {r['usage']}", flush=True)


if __name__ == "__main__":
    main()
