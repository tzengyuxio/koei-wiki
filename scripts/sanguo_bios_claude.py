#!/usr/bin/env python3
"""Rewrite the Qwen Sanguo bio drafts with Claude, grounded in primary sources.

Sources per person: everything sanguo_bios.py gives Qwen (in-game bios, zh.wikipedia),
plus 《三國志》/《後漢書》 (with 裴注) and 《三國演義》 text from sinotext (sanguo_sources.py),
plus the Qwen draft as a draft to correct. Output is JSON (出典, 列傳, 演義中的形象).

Usage:
  scripts/sanguo_bios_claude.py local [--all | 名 ...] [--model M] [--jobs N]  # claude -p (subscription)
  scripts/sanguo_bios_claude.py run 名1 名2 ... [--model M]   # direct calls, for trials
  scripts/sanguo_bios_claude.py submit [--all | 名 ...] [--model M]  # Message Batches (half price)
  scripts/sanguo_bios_claude.py collect <batch id>
  scripts/sanguo_bios_claude.py show 名                       # print the prompt, no API call
Output: assets/data/sanguo/sanguo-bios-claude.jsonl (re-running a name replaces its line)
run/submit/collect need the anthropic package (use a venv) and ANTHROPIC_API_KEY; local needs only
the claude CLI, and skips names already written by the same model. KAODATA_EXPORT and SINOTEXT
override the source directories.
"""

import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanguo_bios import DATA, context, length_for, load_game_bios  # noqa: E402
from sanguo_sources import peizhu, yanyi, zhengshi  # noqa: E402

DRAFTS = DATA / "sanguo-bios-qwen.jsonl"
OUT = DATA / "sanguo-bios-claude.jsonl"
MODEL = "claude-opus-5-5"
BATCHES = Path.home() / ".cache/koei-wiki/sanguo/batches"  # custom_id -> name, per batch

SYSTEM = """你是三國人物百科的編輯，替人物條目寫定「列傳」與「演義中的形象」。手上有一份草稿，錯誤不少，你要依據提供的資料改寫成定稿。

資料說明：
- 【正史原文】是《三國志》或《後漢書》正文，每段前面是位址。有此人本傳時給本傳，沒有時給提到此人名字的段落（可能混入同名的人，要從上下文判斷）。
- 【裴注】是裴松之注《三國志》所引的其他史書（《魏略》《吳歷》《江表傳》等）與裴松之的按語。有本傳時給本傳的注，沒有時給提到此人名字的注文片段（可能不相干）。只見於裴注的事蹟可以寫，但要註明出處，例如「據《吳歷》記載」；裴松之已指出不可信的說法不要當成事實。
- 【演義原文】是《三國演義》中提到此人的句子，前面的位址第二欄是回數。
- 【遊戲列傳】是光榮遊戲的人物介紹，常把演義和正史混在一起；13、14 代的「史實」段指正史。
- 【維基百科】主要依正史，但可能有錯，也可能是別人或泛稱的條目。
- 【草稿】是另一個模型寫的，常見錯誤：事實錯誤或張冠李戴、照抄維基的錯、同義重複、用詞不準、偏題、演義段寫了不該寫的內容、日文直譯腔。

規則：
1. 正史事蹟以【正史原文】為準，其次是【裴注】，再其次是維基百科；衝突時依原文，《三國志》與《後漢書》不同時依《三國志》。讀原文要先確認每個動作的主詞與詞義，不要把旁人的事套到此人身上（例如「斬首破敵」是斬殺敵兵，不是斬殺敵將；「陳留孔伷」的陳留是籍貫）。演義情節以【演義原文】為準。資料都沒有的事不要寫；你自己的知識只用來讀懂原文，不用來補充事蹟。
2. 判斷出典：正史或裴注有記載的人物算「正史」，寫史書中的生平；只見於《三國演義》的虛構人物（如周倉）寫演義情節；演義以外的虛構人物（如出自《花關索傳》的鮑三娘）寫出處故事。第一句交代出典，例如「〇〇，字〇〇，〇〇人，東漢末年〇〇的將領。」或「〇〇是《三國演義》虛構的人物，……」。字、籍貫只寫正史有的；演義才有的字要註明出自演義。
3. 「演義中的形象」預設是「無」。只有正史人物、而且演義改動很大時才寫：虛構了重要情節、改了結局或死法、明顯誇大或貶低。寫明演義怎麼寫、與正史哪裡不同。提供的原文只是部分史料，此人的事也可能記在別人的傳裡：不能確定史書沒有的事，不要說成演義虛構，也不要寫「正史沒有」「史書都沒有記載」；只寫演義怎麼寫，以及原文明確寫法不同之處（例如結局、死法不同）。史書已有的事（如孫策與太史慈交手、張飛據水斷橋）不算演義虛構。差異不大、只是照正史敷演，或此人本身是虛構人物，都寫「無」；不要寫「與正史大致相同」這種內容。
4. 紀年：第一次提到某年寫「年號＋年（西元年）」，例如「建安五年（200年）」；之後同一年號可省略西元。年號與西元要對得上。用此人所屬政權的年號：魏人用魏的年號，不用蜀、吳的。
5. 官職、地名、人名照原文；不要改寫成意思不同的詞（例如劉備東征是伐吳，不是攻打荊州）。只寫此人：背景用一句交代，不展開父兄、主君或對手的事蹟。只見於裴注的事要註明書名，但同一本書在同一段連續引用時只標第一次，不要每句都寫「據《某書》」。
6. 不要同義重複，不要寫「可見」「顯示」之類解讀前一句的句子，不要誇大或抒情，不要寫「本條目」「綜上所述」。不要談資料本身：不寫「據維基百科」「史書沒有記載」「此後不見記載」「生卒年不詳」「〈某傳〉記載」「沒有為他立傳」「事蹟見於《某書》」「據裴注記載」，不加「（《後漢書》作……）」這類異文註，不討論史學爭議；結局不明就不寫結局。註明裴注引書（如「據《吳歷》記載」）不在此限。不用日文直譯詞（討伐隊、離反、武將登用等），用中文史書的說法。
7. 不要提到遊戲、能力值或光榮。使用臺灣繁體中文與全形標點，自然分段，不加標題、清單、連結或 Markdown 記號。
8. 字數：「列傳」{length}；「演義中的形象」最多 300 字，不要比列傳長。寫完先數字數，超過就刪到上限以內。字數是硬上限，寧短勿長：不要逐段翻譯本傳，挑此人最重要的幾件事寫，核心人物也只挑五、六件大事，不要每場戰役、每次封賞都寫；作戰細節、官職遷轉、詔令、旁人言論、史評只留最關鍵的。資料少就寫短，不用背景或旁人的事湊字數。

以 JSON 回答：origin 是出典（"正史"、"演義" 或 "其他"），bio 是列傳，yanyi 是演義中的形象（不寫時為 "無"）。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "origin": {"type": "string", "enum": ["正史", "演義", "其他"]},
        "bio": {"type": "string"},
        "yanyi": {"type": "string"},
    },
    "required": ["origin", "bio", "yanyi"],  # ASCII keys: the CLI passes the schema as a tool
    "additionalProperties": False,
}



def max_length(row: dict) -> str:
    """An explicit ceiling: "約 N 字" ranges were read as targets and overrun by a third."""
    text = length_for(row)
    if "1000" in text:
        return "最多 900 字，劉備、曹操、孫權、諸葛亮等核心人物最多 1200 字"
    if "600" in text:
        return "最多 550 字"
    return "最多 300 字；資料少就如實簡短"


def load_inputs():
    rows = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-mapping.csv", encoding="utf-8"))}
    old = {(r := json.loads(line))["name"]: r for line in open(DATA / "sanguo-bios.jsonl", encoding="utf-8") if line.strip()}
    new = {r["wiki名"]: r for r in csv.DictReader(open(DATA / "persons-new.csv", encoding="utf-8"))}
    drafts = {(r := json.loads(line))["name"]: r for line in open(DRAFTS, encoding="utf-8") if line.strip()}
    return rows, old, new, drafts, load_game_bios()


def params(wiki: str, inputs, model: str) -> tuple[dict, dict]:
    rows, old, new, drafts, bios = inputs
    row, name = rows[wiki], wiki.partition("_")[0]
    ctx, used, wiki_title = context(wiki, row, old.get(wiki, {}), new.get(wiki, {}), bios)
    if zs := zhengshi(name):
        ctx.append(f"【正史原文】\n{zs}")
    if pz := peizhu(name):
        ctx.append(f"【裴注】\n{pz}")
    if yy := yanyi(name):
        ctx.append(f"【演義原文】\n{yy}")
    if d := drafts.get(wiki):
        ctx.append(f"【草稿】\n列傳：{d['bio']}\n演義中的形象：{d['yanyi'] or '無'}")
    user = "\n\n".join(ctx) + f"\n\n請依以上資料寫定{name}的列傳與演義中的形象。"
    sources = {"games": used, "wikipedia": wiki_title, "sinotext": bool(zs), "peizhu": bool(pz), "yanyi_text": bool(yy)}
    return {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM.format(length=max_length(row)),
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
    }, sources


def record(wiki: str, message, sources: dict) -> dict:
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"{wiki}: stop_reason {message.stop_reason}")
    data = json.loads(next(b.text for b in message.content if b.type == "text"))
    yanyi_text = data["yanyi"].strip()
    return {
        "name": wiki,
        "origin": data["origin"],
        "bio": data["bio"].strip(),
        "yanyi": "" if yanyi_text.strip("「」。 ") == "無" else yanyi_text,
        "sources": sources,
        "model": message.model,
        "usage": {"input": message.usage.input_tokens, "output": message.usage.output_tokens},
    }


def local(wiki: str, inputs, model: str) -> dict:
    """One person through the claude CLI (subscription quota): no tools, no settings, no session."""
    p, sources = params(wiki, inputs, model)
    cmd = ["claude", "-p", "--model", model, "--effort", p["output_config"]["effort"], "--tools", "",
           "--system-prompt", p["system"], "--json-schema", json.dumps(SCHEMA, ensure_ascii=False),
           "--output-format", "json", "--no-session-persistence", "--setting-sources", "",
           "--strict-mcp-config", "--disable-slash-commands"]
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # keep it on the subscription
    out = subprocess.run(cmd, input=p["messages"][0]["content"], capture_output=True, text=True,
                         env=env, cwd=BATCHES.parent, timeout=900)
    res = json.loads(out.stdout)
    if res.get("is_error") or not res.get("structured_output"):
        raise RuntimeError(f"{wiki}: {res.get('subtype')} {str(res.get('result'))[:200]}")
    data, usage = res["structured_output"], res.get("usage", {})
    yanyi_text = data["yanyi"].strip()
    return {
        "name": wiki,
        "origin": data["origin"],
        "bio": data["bio"].strip(),
        "yanyi": "" if yanyi_text.strip("「」。 ") == "無" else yanyi_text,
        "sources": sources,
        "model": model,
        "usage": {"input": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                  + usage.get("cache_creation_input_tokens", 0), "output": usage.get("output_tokens", 0)},
    }


def save(records: list[dict]) -> None:
    done = {}
    if OUT.exists():
        done = {(r := json.loads(line))["name"]: r for line in OUT.read_text(encoding="utf-8").splitlines() if line}
    done.update({r["name"]: r for r in records})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()), encoding="utf-8")


def main() -> None:
    cmd, args = sys.argv[1], sys.argv[2:]
    model = args[args.index("--model") + 1] if "--model" in args else MODEL
    names = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--model")]
    if cmd == "collect":
        import anthropic
        client = anthropic.Anthropic()
        sources = json.loads((BATCHES / f"{names[0]}.json").read_text(encoding="utf-8"))
        records = []
        for result in client.messages.batches.results(names[0]):
            if result.result.type != "succeeded":
                print(f"FAILED {result.custom_id}: {result.result.type}")
                continue
            wiki = sources[result.custom_id]["name"]
            try:
                records.append(record(wiki, result.result.message, sources[result.custom_id]["sources"]))
            except Exception as e:  # noqa: BLE001  keep the rest; failed names are resubmitted
                print(f"FAILED {wiki}: {e}")
        save(records)
        print(f"saved {len(records)}")
        return

    inputs = load_inputs()
    if "--all" in args:
        names = list(inputs[3])  # everyone with a Qwen draft
    if cmd == "show":
        p, _ = params(names[0], inputs, model)
        print(p["system"] + "\n\n=====\n\n" + p["messages"][0]["content"])
        return
    if cmd == "local":
        jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 4
        names = [n for n in names if not n.isdigit()]
        if OUT.exists():  # resume: skip what this model already wrote
            done = {r["name"] for line in OUT.read_text(encoding="utf-8").splitlines() if line
                    and (r := json.loads(line))["model"] == model}
            names = [n for n in names if n not in done]
        print(f"{len(names)} to do", flush=True)
        with ThreadPoolExecutor(jobs) as pool:
            for wiki, fut in [(w, pool.submit(local, w, inputs, model)) for w in names]:
                try:
                    r = fut.result()
                except Exception as e:  # noqa: BLE001  keep going; a re-run retries the failures
                    print(f"FAILED {wiki}: {e}", flush=True)
                    continue
                save([r])
                print(f"{r['name']}: {r['origin']}, {len(r['bio'])}+{len(r['yanyi'])} chars, {r['usage']}", flush=True)
        return
    import anthropic
    client = anthropic.Anthropic()
    if cmd == "run":
        def one(wiki):
            p, sources = params(wiki, inputs, model)
            with client.messages.stream(**p) as stream:
                return record(wiki, stream.get_final_message(), sources)
        with ThreadPoolExecutor(8) as pool:
            records = list(pool.map(one, names))
        save(records)
        for r in records:
            print(f"{r['name']}: {r['origin']}, {len(r['bio'])}+{len(r['yanyi'])} chars, {r['usage']}")
    elif cmd == "submit":
        requests, sources = [], {}
        for i, wiki in enumerate(names):
            p, src = params(wiki, inputs, model)
            requests.append({"custom_id": f"p{i}", "params": p})
            sources[f"p{i}"] = {"name": wiki, "sources": src}
        batch = client.messages.batches.create(requests=requests)
        BATCHES.mkdir(parents=True, exist_ok=True)
        (BATCHES / f"{batch.id}.json").write_text(json.dumps(sources, ensure_ascii=False), encoding="utf-8")
        print(f"submitted {len(requests)} as {batch.id}")


if __name__ == "__main__":
    main()
