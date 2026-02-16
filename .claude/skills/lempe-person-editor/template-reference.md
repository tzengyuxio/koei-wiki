# Person Entry Template Reference

This is the canonical structure for all person entries under `人物/拿破崙時代/`.

## Full Template

```markdown
---
title: {遊戲中文名}
description: "{簡短人物描述}"
published: true
date: {YYYY-MM-DDTHH:MM:SS.000Z}
tags: lempe
editor: markdown
dateCreated: {YYYY-MM-DDTHH:MM:SS.000Z}
---

## 基本資料

| 項目 | 內容 |
| :--- | :--- |
| 中文譯名 | {真實中文譯名} |
| 原文 | {真實原名} |
| 遊戲作品中名稱 | {遊戲日文名} / {遊戲英文名} / {遊戲中文名} |
| 國籍 | {國籍} |

## 遊戲數值

| ID | 政治 | 財政 | 補給 | 建設 | 指揮 | 步兵 | 騎兵 | 砲兵 | 冷靜 | 勇敢 | 魅力 | 幸運 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| {ID} | {政治} | {財政} | {補給} | {建設} | {指揮} | {步兵} | {騎兵} | {砲兵} | {冷靜} | {勇敢} | {魅力} | {幸運} |

## 人物畫像

<div style="display: flex; gap: 1em; align-items: flex-end;">
<figure>
<img src="/assets/portraits/{snake_case_real_name}.jpg" alt="{真實中文譯名}肖像" height="320">
<figcaption>{真實中文譯名}的肖像</figcaption>
</figure>
<figure>
<img src="/assets/portraits/gamefaces/LEMPE_DOS_F{顏:04d}.png" alt="{遊戲中文名}遊戲頭像" height="320">
<figcaption>遊戲中的頭像</figcaption>
</figure>
</div>

## 列傳

{300-1000 字的人物傳記}

## References

- [{真實中文譯名} - 维基百科]({中文Wiki URL})
- [{真實原名} - Wikipedia]({英文Wiki URL})
```

## Field Notes

| Field | Source | Notes |
|:------|:-------|:------|
| title | `lempe-persons-full.csv` → 遊戲中文名 | Also used as filename |
| description | Manual | Brief identity description from CSV 備註 or research |
| 中文譯名 | `lempe-persons-full.csv` → 真實中文譯名 | Real-world Chinese name |
| 原文 | `lempe-persons-full.csv` → 真實原名 | Original name in native language |
| 遊戲日文名 | `lempe-persons-full.csv` → 遊戲日文名 | Japanese katakana from game |
| 遊戲英文名 | `lempe-persons-full.csv` → 遊戲英文名 | English name from game |
| ID | `lempe-persons-s1-zh.csv` → ID | Person index (0-254) |
| 顏 | `lempe-persons-s1-zh.csv` → 顏 | **Face image index** (NOT same as ID) |
| Stats | `lempe-persons-s1-zh.csv` | Ranks: A/B/C/D; Traits: 冷靜/單純/勇氣/膽小/魅力/幸運 (blank if none) |
| 國籍 | `lempe-persons-s1-zh.csv` → 國籍 | In-game nationality |
| Portrait filename | Manual | `{lowercase_snake_case_of_real_name}.jpg` |
| Wiki URLs | `lempe-persons-full.csv` → 英文Wiki, 中文Wiki | May be `nan` for ZH |

## Trait Values

Stats columns (冷靜/勇敢/魅力/幸運) use specific terms:

| Column | Positive | Negative | Blank |
|:-------|:---------|:---------|:------|
| 冷靜 | 冷靜 | 單純 | (empty) |
| 勇敢 | 勇氣 | 膽小 | (empty) |
| 魅力 | 魅力 | — | (empty) |
| 幸運 | 幸運 | — | (empty) |
