"""Primary-source excerpts for 三國 persons, read from sinotext (《三國志》《後漢書》《三國演義》).

sinotext (~/works/sinotext, or $SINOTEXT) keeps each book as <book>/<卷>.tsv with columns 段, 篇, 正文;
an address is <book>.<卷>.<段>. 篇 names the biography's subject, e.g. "呂範／子 據" (呂據 inside 呂範's).
裴松之's notes to 三國志 are in <卷>.notes.tsv (段, 位置, 注), attached to a paragraph of the main text.

  python3 scripts/sanguo_sources.py 呂據 [--yanyi]    # print what a person gets
"""

import csv
import functools
import os
import re
import sys
from pathlib import Path

SINOTEXT = Path(os.environ.get("SINOTEXT", Path.home() / "works/sinotext"))
# 卷1-3 have no 篇; 后妃傳 titles the subject by posthumous title, not by the name the wiki uses.
VOLUME_SUBJECT = {("sanguozhi", "001"): "曹操", ("sanguozhi", "002"): "曹丕", ("sanguozhi", "003"): "曹叡"}
PIAN_ALIAS = {"武宣卞皇后": "卞氏", "文昭甄皇后": "甄氏", "文德郭皇后": "郭氏", "先主甘皇后": "甘氏",
              "吳夫人": "吳國太", "齊王": "曹芳", "高貴鄉公": "曹髦", "陳留王": "曹奐"}
BIO_CAP = 9000      # chars of a person's own biography
MENTION_CAP = 3000  # chars of other paragraphs naming the person
YANYI_CAP = 4000    # chars of 演義 sentences naming the person
NOTE_CAP = 6000    # chars of 裴注 on the person's own biography
VARIANT = {"于": "於", "於": "于", "糜": "麋", "麋": "糜", "彤": "肜", "肜": "彤", "婁": "娄", "娄": "婁", "協": "恊", "恊": "協", "淩": "凌", "凌": "淩"}  # the texts mix these (於詮, 傅肜)
# Names the wiki takes from 演義 where the histories write another: 呂義 is 呂乂 in 三國志.
NAME_ALIAS = {"呂義": "呂乂", "吳懿": "吳壹", "孫尚香": "孫夫人", "孫魯班": "全公主", "孫魯育": "朱公主",
              "步練師": "步夫人", "沙摩柯": "沙靡柯", "滕脩": "滕循",
              "田楷": "田揩", "王子服": "王服", "費耀": "費曜",
              "麴義": "曲義", "龔都": "共都", "黨均": "党均", "陳蘭": "陳簡", "高翔": "高詳"}
# Kin named by given name only inside a relative's biography: 典韋傳 "子滿" is 典滿.
KIN = "子|弟|從弟|兄|從兄|孫|兄子|弟子|從子|姪"
NOTE_WINDOW = 800   # chars kept on each side of the name in other notes


def subjects(book: str, vol: str, pian: str) -> set[str]:
    """Person names a 篇 is about: "袁紹／子　譚、熙、尚" -> 袁譚, 袁熙, 袁尚; "燕王宇" -> 曹宇."""
    if (book, vol) in VOLUME_SUBJECT:
        return {VOLUME_SUBJECT[(book, vol)]}
    parts = [p.strip() for p in pian.split("／")]
    surname = re.sub(r"^(先主|後主).*", "劉", parts[0])[:1]
    out = set()
    for part in parts:
        if part in PIAN_ALIAS:
            out.add(PIAN_ALIAS[part])
            continue
        if book == "sanguozhi" and vol in ("019", "020") and (m := re.search(r"(?:王|公|公子)曹?(\S{1,2})$", part)):
            out.add("曹" + m.group(1))  # 魏 princes: 任城王曹彰, 燕王宇
            continue
        part = re.sub(r"^附\s*", "", part.replace("　", " "))
        head, _, rest = part.rpartition(" ")
        for item in rest.split("、"):
            item = item.removesuffix("等")
            out.add(item)
            if head and len(item) <= 2 and re.search("子|弟|孫|侄|甥", head):
                out.add(surname + item)  # 呂範／子 據 -> 呂據 (also keeps 霍弋 from "子 霍弋")
    return out


@functools.cache
def book(name: str) -> list[tuple[str, frozenset, str]]:
    """[(address, subjects of its 篇, text)] in reading order."""
    out = []
    for f in sorted((SINOTEXT / name).glob("[0-9]*.tsv")):
        if f.name.endswith(("notes.tsv", "refs.tsv")):
            continue
        vol = f.stem
        for row in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t"):
            out.append((f"{name}.{vol}.{row['段']}", frozenset(subjects(name, vol, row["篇"] or "")), row["正文"]))
    return out


@functools.cache
def notes() -> list[tuple[str, str]]:
    """裴注 as [(address of the paragraph it annotates, text)]."""
    out = []
    for f in sorted((SINOTEXT / "sanguozhi").glob("[0-9]*.notes.tsv")):
        vol = f.name.split(".")[0]
        for row in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t"):
            out.append((f"sanguozhi.{vol}.{row['段']}", row["注"]))
    return out


def spellings(name: str) -> set[str]:
    """The name plus its variant spellings: 于糜 -> 于糜, 於糜, 于麋, 於麋."""
    out = set()
    for n in {name, NAME_ALIAS.get(name, name)}:
        spelled = {""}
        for c in n:
            spelled = {o + v for o in spelled for v in {c, VARIANT.get(c, c)}}
        out |= spelled
    return out


def find(names: set[str], text: str) -> int:
    return min((i for n in names if (i := text.find(n)) >= 0), default=-1)


def take(paras: list[tuple[str, str]], cap: int) -> str:
    lines, used = [], 0
    for addr, text in paras:
        if used + len(text) > cap:
            lines.append(f"……（以下省略，共 {len(paras)} 段）")
            break
        lines.append(f"[{addr}] {text}")
        used += len(text)
    return "\n".join(lines)


def zhengshi(name: str) -> str:
    """Own biography in 三國志 / 後漢書, else other paragraphs naming the person."""
    names = spellings(name)
    own = [(a, t) for b in ("sanguozhi", "houhanshu") for a, s, t in book(b) if names & s]
    if own:
        return take(own, BIO_CAP)
    if name.endswith("氏") or len(name) < 2:  # 張氏 matches everyone's mother
        return ""
    surname, given = name[0], name[1:]  # two-char surnames (公孫, 司馬) are handled below
    if name[:2] in ("公孫", "司馬", "諸葛", "夏侯", "皇甫", "太史", "令狐", "毌丘", "鍾離", "東方"):
        surname, given = name[:2], name[2:]
    mentions = [(a, t) for b in ("sanguozhi", "houhanshu") for a, s, t in book(b)
                if find(names, t) >= 0
                or (given and any(x.startswith(surname) for x in s) and re.search(rf"(?:{KIN}){re.escape(given)}", t))]
    return take(mentions, MENTION_CAP)


def peizhu(name: str) -> str:
    """裴注 on the person's own biography, else excerpts of notes naming the person."""
    names = spellings(name)
    own = {a for a, s, _ in book("sanguozhi") if names & s}
    if own:
        # A shared 篇 (夏侯惇／子 楙) annotates the father too: notes naming the person come first.
        given = name[2:] if len(name) > 2 else name[1:]
        mine = [(f"{a} 注", t) for a, t in notes() if a in own]
        return take(sorted(mine, key=lambda n: given not in n[1]), NOTE_CAP)
    if len(name) < 2:
        return ""
    hits = []
    for a, t in notes():
        if (i := find(names, t)) >= 0:
            lo, hi = max(0, i - NOTE_WINDOW), i + len(name) + NOTE_WINDOW
            hits.append((f"{a} 注", ("……" if lo else "") + t[lo:hi] + ("……" if hi < len(t) else "")))
    return take(hits, NOTE_CAP)


def yanyi(name: str) -> str:
    """Sentences of 三國演義 naming the person, with their chapter."""
    if name.endswith("氏") or len(name) < 2:
        return ""
    hits, names = [], spellings(name)
    for addr, _, text in book("sanguoyanyi"):
        for s in re.findall(r"[^。！？]*[。！？」』]*", text.replace("／", "")):
            if find(names, s) >= 0:
                hits.append((addr, s.strip()))
    return take(hits, YANYI_CAP)


if __name__ == "__main__":
    for n in [a for a in sys.argv[1:] if not a.startswith("--")]:
        print(f"== {n} 正史 ==\n{zhengshi(n)}")
        print(f"== {n} 裴注 ==\n{peizhu(n)}")
        if "--yanyi" in sys.argv:
            print(f"== {n} 演義 ==\n{yanyi(n)}")
