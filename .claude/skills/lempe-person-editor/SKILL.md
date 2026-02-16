---
name: lempe-person-editor
description: "Create and edit L'Empereur (ランペルール) character wiki entries. Use when adding new person pages, updating bios, fixing portraits, or working with lempe-persons CSV data."
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, WebFetch, WebSearch
argument-hint: "[character-name or ID]"
---

# L'Empereur Person Editor

Create or edit character entries for the L'Empereur (ランペルール) game wiki.

## Quick Reference

- **Person files**: `人物/拿破崙時代/{遊戲中文名}.md`
- **Template**: `assets/person_template.md`
- **Main CSV**: `assets/data/lempereur/lempe-persons-full.csv`
- **Stats CSV**: `assets/data/lempereur/lempe-persons-s1-zh.csv`
- **Historical portraits**: `assets/portraits/{snake_case_name}.jpg`
- **Game faces**: `assets/portraits/gamefaces/LEMPE_DOS_F{顏:04d}.png`
- **Review log**: `assets/review_log.md`

## Workflow

### Creating a new entry

1. Look up the character in `lempe-persons-full.csv` by ID or name.
2. Get game stats from `lempe-persons-s1-zh.csv`.
3. **Critical**: The game face image uses the `顏` column value, NOT the `ID` column. Format: `LEMPE_DOS_F{顏:04d}.png`.
4. Research the historical person via Wikipedia (EN + ZH).
5. Download historical portrait if available (from Wikipedia `og:image` or Wikimedia Commons).
6. Generate the md file following the template in [template-reference.md](template-reference.md).
7. Write a biography (列傳) of 300–1000 characters.

### Editing an existing entry

1. Read the existing file first.
2. Cross-reference with CSV data to verify correctness.
3. When rewriting a biography, research via Wikipedia and other sources.

## Data Sources

See [data-reference.md](data-reference.md) for full CSV column descriptions.

### Key CSV: `lempe-persons-full.csv`

Columns: 編號, 遊戲英文名, 遊戲中文名, 遊戲日文名, 真實原名, 真實中文譯名, 英文Wiki, 中文Wiki, 備註, ID, 姓名, 中文版, 英文版, 國家, **顏**, 政治...幸運

### Key CSV: `lempe-persons-s1-zh.csv`

Columns: ID, 姓名, **顏**, 政治, 財政, 補給, 建設, 指揮, 步兵, 騎兵, 砲兵, 冷靜, 勇敢, 魅力, 幸運, 城市, 國籍

## Critical Rules

### Game Face Mapping

**The `顏` (face) column is the game face image index, NOT the `ID` column.**

- Many characters share face images or have mismatched ID/face values.
- Always use: `LEMPE_DOS_F{顏:04d}.png` (zero-padded to 4 digits).
- Example: ID=55 (喬治三世) has 顏=58, so use `LEMPE_DOS_F0058.png`.

### File Naming

- Filename = `遊戲中文名.md` (the game's Chinese localized name).
- This may differ from the real-world Chinese translation (真實中文譯名).

### Biography (列傳)

- 300–1000 Chinese characters. No filler text.
- Use real-world names in prose, not game names.
- Mention birth/death years in the first sentence.
- Must be based on verifiable historical sources. If unknown, write `（待考證）`.

### Inter-linking

When mentioning other characters, link using: `[真實姓名](/人物/拿破崙時代/遊戲中文名)`

Example: `他在[拉納](/人物/拿破崙時代/列寧斯)元帥麾下服役。`

### Portrait Layout

Both portraits are displayed side-by-side using flexbox with `<figure>/<figcaption>`:

```html
<div style="display: flex; gap: 1em; align-items: flex-end;">
<figure>
<img src="/assets/portraits/{snake_case}.jpg" alt="{中文譯名}肖像" height="320">
<figcaption>{中文譯名}的肖像</figcaption>
</figure>
<figure>
<img src="/assets/portraits/gamefaces/LEMPE_DOS_F{顏:04d}.png" alt="{遊戲中文名}遊戲頭像" height="320">
<figcaption>遊戲中的頭像</figcaption>
</figure>
</div>
```

### References

- Include both EN and ZH Wikipedia links when available.
- If ZH wiki link is `nan` or missing, only include EN link.

## Known Issues

- `布律納.md` (Guillaume Brune) is NOT in the game's 255-person roster; no game face.
- EN/ZH/JP localized names often differ completely. Japanese katakana (from hima.que.ne.jp) is the most reliable identifier.
- Some characters are duplicates pointing to the same historical person (see `review_log.md` section 1).
- 15 characters remain unidentified (see MEMORY.md for the list).
