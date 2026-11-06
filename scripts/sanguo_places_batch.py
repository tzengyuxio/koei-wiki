#!/usr/bin/env python3
"""Write the Sanguo place / 州 entry facts and intros with the Claude Message Batches API.

Reads ~/.cache/koei-wiki/place-sources.jsonl (sanguo_places_sources.py) and writes
assets/data/sanguo/place-entries.jsonl, which build_sanguo_places.py turns into pages.

Usage (needs ANTHROPIC_API_KEY; the anthropic SDK comes from uv, nothing is installed in the repo):
  uv run --with anthropic python scripts/sanguo_places_batch.py submit [--only 名,名…] [--limit N]
  uv run --with anthropic python scripts/sanguo_places_batch.py status
  uv run --with anthropic python scripts/sanguo_places_batch.py collect
Add --set suikoden for the Suikoden 州 (sources from suikoden_places_sources.py, output
assets/data/suikoden/place-entries.jsonl). Entries already in the output are skipped on submit.
"""

import json
import re
import sys
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / ".cache/koei-wiki"
SET = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "sanguo"
OUT = ROOT / f"assets/data/{SET}/place-entries.jsonl"
SOURCES = CACHE / ("place-sources.jsonl" if SET == "sanguo" else f"{SET}-place-sources.jsonl")
STATE = CACHE / ("places-batch.json" if SET == "sanguo" else f"{SET}-places-batch.json")
MODEL = "claude-opus-5-5"
KBD = {"san1-pc98": "三1", "san2-pc98": "三2", "san3-pc98": "三3", "san4pk-pc98": "三4", "san5pk-pc98": "三5",
       "san6pk-win": "三6", "san7pk-win": "三7", "san8pk-win": "三8", "san9pk-win": "三9", "san10pk-win": "三10",
       "san11pk-win": "三11", "san12pk-win": "三12", "san13pk-win": "三13", "san14pk-win": "三14"}

SYSTEM = """你替 koei.wiki（光榮歷史模擬遊戲百科，繁體中文）撰寫三國志系列「地點條目」的事實欄位與簡介。條目以遊戲中的地名為單位；你拿到的是這個地名在各代遊戲中的用法、漢郡志資料庫在東漢永和五年（140 年，《續漢書・郡國志》的基準年）同名的郡縣，以及維基百科的導言。

規則：
- 只寫來源支持或三國史常識中確定的事；不確定就不寫，欄位留空字串。維基百科導言可能講的是別的同名地方（如今日的行政區、別的朝代），不相干就不用。
- 漢末政區：這個名稱在東漢末年對應的政區，以《續漢書・郡國志》為準，從郡級寫起：豫章 → 豫章郡；鄱陽 → 豫章郡鄱陽縣；吳 → 吳郡吳縣（郡縣同名兩級都寫）；洛陽 → 河南尹雒陽縣。關、山、渡口等不是政區的地點，寫它所在的郡縣，如「河南尹成皋縣境」。沒有對應的（如遊戲自創的西涼）寫「無」。
- 政區等級：寫實際的類別，郡級是郡、王國、尹、屬國，縣級是縣、侯國、道、邑（不要寫「郡級」「縣級」）；郡縣同名取高者（吳 → 郡）；關、山、戰場等寫「非政區」；沒有對應寫「無」。
- 漢末所屬州：東漢的州（十三州）。遊戲把它歸到不同的州時，在後面加注，如「青州（遊戲多歸冀州）」。
- 今地：今日的位置，寫到省與市縣，如「江西省九江市」；不確定就留空。
- 州條目（kind 為「州」）：han_division 寫漢末的治所郡縣，han_level 寫「州」；遊戲自創的州（如荊北、青徐、南中）說明它涵蓋漢末哪些州郡。
- 簡介：繁體中文、全形標點、自然分段、不加標題、不加連結。寫這個地名在漢末三國的位置、沿革（設置、改名、治所遷移；140 年之後的改制寫在這裡）、在三國時期的地位與重要事件。戰役一兩句帶過。史料豐富的都市與州約 300–600 字；縣級地點、港、府、小據點 80–200 字即可，不要湊字數。不要寫遊戲機制，不要逐代列舉遊戲資料（頁面上另有表格）。
- 遊戲寫法的錯字（如東來、盧陵港）只是遊戲的問題，簡介用正確寫法即可。
- 事件：在此發生、條目可以連結的著名事件，最多五項，依時間排，格式「年份：事件名」，如「200 年：官渡之戰」；沒有就給空陣列。
- refs：從提供的維基百科條目中，選出確實講這個地點的標題（照原樣）；沒有就給空陣列。
- description：一句話描述（30 字內），如「東漢豫章郡的屬縣，三國時東吳的軍事重鎮」。

只輸出一個 JSON 物件，不要其他文字：
{"description": "", "han_division": "", "han_level": "", "han_province": "", "today": "", "intro": "", "events": [], "refs": []}"""


SUIKODEN_SYSTEM = """你替 koei.wiki（光榮歷史模擬遊戲百科，繁體中文）撰寫《水滸傳・天命之誓》（光榮，1989）的「州條目」事實欄位與簡介。遊戲的地點只有 49 州，條目以州為單位；你拿到的是遊戲資料（州名寫法、城數、相鄰的州）與維基百科的導言。

規則：
- 只寫來源支持或宋史、《水滸傳》（百回本／百二十回本）常識中確定的事；不確定就不寫，欄位留空字串。維基百科導言可能講的是今日的同名行政區或別的朝代，不相干就不用。
- 北宋政區（song_division）：以《宋史・地理志》為準，寫北宋末年（宣和年間，水滸故事的年代）的路與府州，如「京東西路鄆州」「河北東路大名府」「京畿路開封府」。府、州、軍照當時的稱呼。名稱在宋代不存在或對應不明的，寫你確定的部分並在簡介說明。
- 治所（seat）：府州的治所縣，如「須城縣」；不確定留空。
- 今地：今日的位置，寫到省與市縣，如「山東省泰安市東平縣」。
- 遊戲寫法的錯字（窿德、鳳祥、穎州）只是遊戲的問題，條目已改用正確寫法，簡介用正確寫法即可。
- 簡介：繁體中文、全形標點、自然分段、不加標題、不加連結。先寫北宋時的沿革與地位（約 100–250 字），再寫《水滸傳》小說中與此地有關的情節與人物（有就寫，約 100–300 字；沒有就一句帶過或不寫）。分清楚史實與小說。不要寫遊戲機制，不要列遊戲數值。
- 事件：小說中發生在此地的著名情節，最多五項，依回目順序，格式「第 N 回：情節名」，如「第 16 回：智取生辰綱」；回目不確定就不列；沒有就給空陣列。
- refs：從提供的維基百科條目中，選出確實講這個府州（或其今地）的標題（照原樣）；沒有就給空陣列。
- description：一句話描述（30 字內），如「北宋京東西路的州，梁山泊所在之地」。

只輸出一個 JSON 物件，不要其他文字：
{"description": "", "song_division": "", "seat": "", "today": "", "intro": "", "events": [], "refs": []}"""


GAME_SYSTEM = """你替 koei.wiki（光榮歷史模擬遊戲百科，繁體中文）撰寫遊戲的「都市資料一覽」（或州資料一覽）頁面的概要。你拿到的是逆向研究的筆記，裡面有檔案位址、資料結構等技術細節，這些不要寫進概要。

概要寫給玩家看：這一代的地點單位叫什麼（國、州、都市、據點、關、港、府等）、各有幾個、怎麼分等級、打仗時用哪一張戰場地圖（攻城、野戰怎麼決定），以及和前後代相比的特色。繁體中文、全形標點、一到兩段、100–300 字，不加標題、不加連結。筆記標示推定或未確認的，寫成「推定」或不寫。

只輸出一個 JSON 物件，不要其他文字：{"summary": ""}"""


def prompt(src: dict) -> str:
    if src["kind"] == "遊戲":
        return f"作品：{src['entry'][3:]}\n\n筆記：\n{src['notes']}"
    if src["kind"] == "水滸州":
        lines = [f"條目：{src['entry']}（遊戲寫法「{src['writing']}」" + (f"，日文版「{src['nameJa']}」" if src.get("nameJa") else "") + "）",
                 f"城數：{src['cities']}", f"相鄰：{'、'.join(src['adjacent'])}", "", "維基百科導言："]
        return "\n".join(lines + ([f"【{w['title']}】{w['extract']}" for w in src["wikipedia"]] or ["- 無"]))
    games = {}
    for g in src["games"]:
        key = KBD.get(g["dataset"], g["dataset"])
        games.setdefault(key, set()).add(f"{g['level']}，遊戲寫法「{g['writing']}」" + (f"，屬{g['province']}" if g.get("province") else "")
                                         + (f"，轄 {'、'.join(g['members'])}" if g.get("members") else ""))
    lines = [f"條目：{src['entry'].removeprefix('州:')}（{src['kind']}條目）", "", "各代遊戲中的用法："]
    lines += [f"- {k}：{'；'.join(sorted(v))}" for k, v in games.items()]
    lines += ["", "漢郡志（140 年同名的政區）："]
    lines += [f"- {u['name']}（{u['type']}，屬 {' → '.join(u['within']) or '—'}）" + (f"治 {u['seat']}" if u.get("seat") else "")
              for u in src["hanjunzhi"]] or ["- 無"]
    lines += ["", "維基百科導言："]
    lines += [f"【{w['title']}】{w['extract']}" for w in src["wikipedia"]] or ["- 無"]
    return "\n".join(lines)


def load_sources() -> list[dict]:
    return [json.loads(line) for line in SOURCES.read_text(encoding="utf-8").splitlines() if line]


def done() -> set[str]:
    return {json.loads(line)["entry"] for line in OUT.read_text(encoding="utf-8").splitlines() if line} if OUT.exists() else set()


def submit(args: list[str]) -> None:
    only = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    srcs = [s for s in load_sources() if s["entry"] not in done() and (only is None or s["entry"] in only)][:limit]
    ids = {f"p{i:04d}": s["entry"] for i, s in enumerate(srcs)}  # custom_id must be ASCII
    reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
        model=MODEL, max_tokens=8000,
        system=[{"type": "text", "text": {"遊戲": GAME_SYSTEM, "水滸州": SUIKODEN_SYSTEM}.get(s["kind"], SYSTEM), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt(s)}])) for cid, s in zip(ids, srcs)]
    batch = anthropic.Anthropic().messages.batches.create(requests=reqs)
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"batch": batch.id, "ids": ids}, ensure_ascii=False), encoding="utf-8")
    print(f"submitted {batch.id}: {len(reqs)} requests")


def status() -> None:
    b = anthropic.Anthropic().messages.batches.retrieve(json.loads(STATE.read_text(encoding="utf-8"))["batch"])
    print(b.id, b.processing_status, b.request_counts)


def collect() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    client = anthropic.Anthropic()
    ok, bad, usage = 0, [], {"in": 0, "out": 0}
    with OUT.open("a", encoding="utf-8") as f:
        for r in client.messages.batches.results(state["batch"]):
            entry = state["ids"][r.custom_id]
            if r.result.type != "succeeded":
                bad.append(f"{entry}: {r.result.type}")
                continue
            msg = r.result.message
            usage["in"] += msg.usage.input_tokens
            usage["out"] += msg.usage.output_tokens
            text = next((b.text for b in msg.content if b.type == "text"), "")
            m = re.search(r"\{.*\}", text, re.S)
            try:
                data = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                data = None
            if not data:
                bad.append(f"{entry}: unparsable")
                continue
            f.write(json.dumps({"entry": entry, **data, "model": MODEL}, ensure_ascii=False) + "\n")
            ok += 1
    print(f"collected {ok}, failed {len(bad)}; tokens in {usage['in']}, out {usage['out']}")
    for b in bad:
        print("  " + b)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "submit":
        submit(sys.argv[2:])
    elif cmd == "status":
        status()
    elif cmd == "collect":
        collect()
