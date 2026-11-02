#!/usr/bin/env python3
"""Fill the 地圖 section of L'Empereur city entries (地點/*.md) with map data blocks.

- data:map-world   the FC strategic map with a marker on the city's label
- data:map-battle  the city's FC battlefield map (only if assets/maps/lempe/battle/<id>.png exists)

City ID comes from the entry's 遊戲數值 table (0-based, same as the game and famicom-re).
The first run replaces the old placeholder image line; later runs only replace data blocks.

Inputs (copied from famicom-re empereur/output/; map and cities at dddb622, battle maps at 558389e):
  assets/maps/lempe/fc-world.png       map.png, 224x144, palette PNG
  assets/data/lempereur/fc-cities.csv  cities.csv; Map_X/Map_Y are label tiles on the full
                                       map, which map.png shows from tile (3, 5) onward
  assets/maps/lempe/battle/<id>.png    battle/<id>.png, 208x200, one per city (normal, not winter)

Usage: scripts/build_lempe_city_maps.py [--dry-run]
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES = ROOT / "assets/data/lempereur/fc-cities.csv"
MAPS = ROOT / "assets/maps/lempe"
PLACEHOLDER = "![地圖 Placeholder](/assets/placeholder_map.png)"
MAP_W, MAP_H, TILE = 224, 144, 8
ORIGIN = (3, 5)  # tile of map.png's top-left corner on the full map
SCALE = 3
BATTLE_W, BATTLE_H = 208, 200  # 13x12 hex cells of 16px


def block(name: str, body: str) -> str:
    return f"<!-- data:{name} begin -->\n{body}\n<!-- data:{name} end -->"


def world_block(name: str, x: int, y: int) -> str:
    # Position in percent so the marker follows any display size set in CSS.
    left = (x - ORIGIN[0]) * TILE / MAP_W * 100
    top = (y - ORIGIN[1]) * TILE / MAP_H * 100
    return block("map-world", (
        '<figure class="kw-map">\n<div class="kw-map-frame">\n'
        f'<img src="/assets/maps/lempe/fc-world.png" alt="拿破崙 FC 版大地圖：{name}" '
        f'width="{MAP_W * SCALE}" height="{MAP_H * SCALE}">\n'
        f'<span class="kw-map-marker" style="left: {left:.2f}%; top: {top:.2f}%;"></span>\n'
        "</div>\n<figcaption>大地圖（FC 版）</figcaption>\n</figure>"))


def battle_block(name: str, city_id: int) -> str | None:
    if not (MAPS / "battle" / f"{city_id}.png").exists():
        return None
    return block("map-battle", (
        '<figure class="kw-map">\n'
        f'<img src="/assets/maps/lempe/battle/{city_id}.png" alt="拿破崙 FC 版戰場地圖：{name}" '
        f'width="{BATTLE_W * 2}" height="{BATTLE_H * 2}">\n'
        "<figcaption>戰場地圖（FC 版）</figcaption>\n</figure>"))


def replace_or_none(text: str, key: str, body: str) -> str | None:
    pat = re.compile(rf"<!-- data:{key} begin -->.*?<!-- data:{key} end -->", re.S)
    return pat.sub(lambda _: body, text) if pat.search(text) else None


def main() -> None:
    dry = "--dry-run" in sys.argv
    cities = {int(r["Index"]): r for r in csv.DictReader(open(CITIES, encoding="utf-8-sig"))}
    done, skipped = 0, []
    for path in sorted((ROOT / "地點").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "tags: lempe" not in text or "## 地圖" not in text:
            continue
        m = re.search(r"^\| (\d+) \| ", text, re.M)
        if not m or int(m.group(1)) not in cities:
            skipped.append(path.name)
            continue
        city_id = int(m.group(1))
        name = path.stem
        row = cities[city_id]
        blocks = [world_block(name, int(row["Map_X"]), int(row["Map_Y"]))]
        if (b := battle_block(name, city_id)):
            blocks.append(b)
        new = text
        if PLACEHOLDER in new:
            new = new.replace(PLACEHOLDER, "\n\n".join(blocks))
        else:
            for b in blocks:
                key = re.match(r"<!-- data:(\S+) begin", b).group(1)
                replaced = replace_or_none(new, key, b)
                if replaced is not None:
                    new = replaced
                elif key == "map-battle":  # battle map added after the world map was in place
                    new = new.replace("<!-- data:map-world end -->", "<!-- data:map-world end -->\n\n" + b)
        if new != text:
            done += 1
            if not dry:
                path.write_text(new, encoding="utf-8")
    print(f"updated {done}; skipped (no city ID) {skipped}")


if __name__ == "__main__":
    main()
