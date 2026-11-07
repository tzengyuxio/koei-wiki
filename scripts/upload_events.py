#!/usr/bin/env python3
"""Upload the event pictures of the kaodata-re events export to R2 (img.simagame.me), with an index.

Layout (docs/events-format.mkdn「R2 網址」):
  https://img.simagame.me/kaodata/event/<dataset>/index.json
  https://img.simagame.me/kaodata/event/<dataset>/<file>.png
index.json lists every picture with the export's fields plus width and height.

Staged in ~/.cache/koei-wiki/event/<dataset>/ and copied with rclone, same keys and rules as
upload_battlemaps.py (only under kaodata/, --checksum, nothing deleted). Uploading publishes: ask the user first.

Usage: python3 scripts/upload_events.py [dataset ...] [--dry-run]   (default: every exported dataset)
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload_battlemaps import ACCOUNT, png_size, secret  # noqa: E402

EXPORT = Path(os.environ.get("EVENTS_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/events"))
STAGE = Path.home() / ".cache/koei-wiki/event"
DEST = "r2:simagame-images/kaodata/event"
URL = "https://img.simagame.me/kaodata/event/{dataset}/{file}"


def stage(dataset: str) -> Path:
    rows = [json.loads(line) for line in (EXPORT / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines() if line]
    out = STAGE / dataset
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    events = []
    for r in rows:
        assert r["file"].isascii() and "/" not in r["file"], r["file"]
        src = EXPORT / dataset / r["file"]
        shutil.copyfile(src, out / r["file"])
        w, h = png_size(src)
        events.append({**{k: v for k, v in r.items() if k != "dataset"}, "width": w, "height": h})
    index = {"dataset": dataset, "source": "kaodata-re export/koei-wiki/events (koei-events/1)", "events": events}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{dataset}: {len(events)} pictures")
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    datasets = args or sorted(p.stem for p in EXPORT.glob("*.jsonl"))
    env = {**os.environ, "RCLONE_CONFIG_R2_TYPE": "s3", "RCLONE_CONFIG_R2_PROVIDER": "Cloudflare",
           "RCLONE_CONFIG_R2_ACCESS_KEY_ID": secret("access-key-id"),
           "RCLONE_CONFIG_R2_SECRET_ACCESS_KEY": secret("secret-access-key"),
           "RCLONE_CONFIG_R2_ENDPOINT": f"https://{ACCOUNT}.r2.cloudflarestorage.com",
           "RCLONE_CONFIG_R2_NO_CHECK_BUCKET": "true"}
    for ds in datasets:
        out = stage(ds)
        subprocess.run(["rclone", "copy", str(out), f"{DEST}/{ds}", "--checksum",
                        "--header-upload", "Cache-Control: public, max-age=86400", "--transfers", "16",
                        "--stats-one-line", *(["--dry-run"] if "--dry-run" in sys.argv else [])],
                       env=env, check=True)


if __name__ == "__main__":
    main()
