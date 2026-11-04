"""Apply reviewer edits to sanguo-bios-claude.jsonl and mark people reviewed.

Usage: scripts/sanguo_bios_review.py review.jsonl [name,name,...]   # names to skip (re-run instead)
Each review line: {"name", "verdict", "issues", "edits": [{"field": "bio"|"yanyi", "old", "new"}]}.
An edit applies only if old occurs exactly once."""
import json, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "assets/data/sanguo/sanguo-bios-claude.jsonl"
skip = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set()
recs = {(r := json.loads(l))["name"]: r for l in OUT.read_text(encoding="utf-8").splitlines() if l}
stats = {"applied": 0, "missing": 0, "people": 0}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rv = json.loads(line); r = recs.get(rv["name"])
    if not r or rv["name"] in skip:
        continue
    for e in rv.get("edits", []):
        if r[e["field"]].count(e["old"]) == 1:
            r[e["field"]] = r[e["field"]].replace(e["old"], e["new"]).strip(); stats["applied"] += 1
        else:
            stats["missing"] += 1; print("MISS", rv["name"], e["old"][:30])
    r["review"] = {"verdict": rv["verdict"], "issues": rv["issues"]}
    stats["people"] += 1
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs.values()), encoding="utf-8")
print(stats)
