#!/usr/bin/env python3
"""Upload the battle maps of the kaodata-re places export to R2 (img.simagame.me), with an index.

Layout (docs/places-format.mkdn「R2 地圖網址」), shared by every site that uses the maps:
  https://img.simagame.me/kaodata/map/<dataset>/index.json
  https://img.simagame.me/kaodata/map/<dataset>/battlefield/<name>.png
<name> is the map's own number or file name in the game, ASCII, plus a descriptor where the game has
several variants (Suikoden seasons: 01-spring.png). index.json maps each image to the places that use it
and each place to its images.

The files are staged in ~/.cache/koei-wiki/map/<dataset>/ and copied with rclone (same bucket and
convention as kaodata's faces, kaodata docs/deploy.md): keys from the macOS Keychain service
simagame-images-rw (never printed), only under kaodata/, --checksum (changed files are re-uploaded,
nothing is deleted), cached for a day. Uploading publishes: ask the user first.

Usage: python3 scripts/upload_battlemaps.py [dataset ...] [--dry-run]   (default: every dataset with maps)
"""

import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

EXPORT = Path(os.environ.get("PLACES_EXPORT", Path.home() / "works/kaodata-re/export/koei-wiki/places"))
STAGE = Path.home() / ".cache/koei-wiki/map"
ACCOUNT = "2e77a35ca1c0f7a24a7dc67348a9de3d"  # Cloudflare account of the bucket (kaodata scripts/r2.ts)
DEST = "r2:simagame-images/kaodata/map"
URL = "https://img.simagame.me/kaodata/map/{dataset}/{path}"
SEASONS = {"春": "spring", "夏": "summer", "秋": "autumn", "冬": "winter"}


def map_path(m: dict) -> str:
    """Export battlemap entry -> path under map/<dataset>/: battlefield/<game name>[-<season>].png."""
    file = Path(m["file"])
    if m.get("season"):
        name = f"{file.stem}-{SEASONS[m['season']]}"
    elif file.parent != Path("."):  # field/01.png and castle/01.png are different maps (信3, 信4)
        name = f"{file.parent.as_posix().replace('/', '-')}-{file.stem}"
    else:
        name = file.stem
    assert name.isascii(), name
    return f"battlefield/{name}.png"


def map_url(dataset: str, m: dict) -> str:
    return URL.format(dataset=dataset, path=map_path(m))


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def stage(dataset: str) -> Path:
    rows = [json.loads(line) for line in (EXPORT / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines() if line]
    out = STAGE / dataset
    if out.exists():
        shutil.rmtree(out)
    maps, places = {}, []
    for p in rows:
        used = []
        for m in p.get("battlemaps", []):
            path = map_path(m)
            if path not in maps:
                src = EXPORT / dataset / m["file"]
                (out / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, out / path)
                w, h = png_size(src)
                maps[path] = {"file": path, "width": w, "height": h, "places": []}
            use = {"id": p["id"], "name": p["name"], "role": m["role"]}
            use.update({k: m[k] for k in ("from", "season") if k in m})
            maps[path]["places"].append(use)
            used.append(path)
        if used:
            places.append({"id": p["id"], "name": p["name"], "battlefield": list(dict.fromkeys(used))})
    index = {"dataset": dataset, "source": "kaodata-re export/koei-wiki/places (koei-places/1)",
             "battlefield": sorted(maps.values(), key=lambda x: x["file"]), "places": places}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{dataset}: {len(maps)} maps, {len(places)} places")
    return out


def secret(account: str) -> str:
    return subprocess.run(["security", "find-generic-password", "-s", "simagame-images-rw", "-a", account, "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    datasets = args or sorted(d.name for d in EXPORT.iterdir() if d.is_dir() and any(d.rglob("*.png")))
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
