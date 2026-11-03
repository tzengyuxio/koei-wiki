---
title: README
description: 
published: false
date: 2026-11-02T12:00:00.000Z
tags: 
editor: markdown
dateCreated: 2023-02-13T11:37:34.739Z
---

# KOEI Wiki

光栄遊戲百科事典（[koei.wiki](https://koei.wiki/)）的內容 repo：光榮歷史模擬遊戲的人物、地點、用語與遊戲資料。

## 網站與 repo

- 網站以 [Wiki.js](https://js.wiki/) 架設，內容從本 repo 的 `main` 同步，git 是正本。
- `.md` 會成為網站頁面；不上站的文件（凡例、決策紀錄、模板、資料說明）用 `.mkdn`，或在 front matter 寫 `published: false`。
- 網站樣式的正本是 `assets/wikijs/theme.css`。條目只寫 `kw-*` class，不寫 `style`。

## 目錄

| 路徑 | 內容 |
| :--- | :--- |
| `人物/`、`地點/`、`用語/`、`事件/`、`遊戲/` | 條目（人物依時代分子目錄，其餘扁平） |
| `更新日誌/` | 對讀者的更新履歷 |
| `assets/` | 模板（`*.mkdn`）、圖片、資料（`data/`）、站台 CSS（`wikijs/`） |
| `scripts/` | 產生與維護條目的 Python 腳本 |
| `EDITORIAL.mkdn` | 編輯凡例（條目結構、連結、圖片、資料區塊標記） |
| `DECISIONS.mkdn` | 架構決策紀錄 |
| `BACKLOG.mkdn` | 待辦 |

## 資料產生的條目

部分段落由 script 從資料產生，包在 `<!-- data:<名稱> begin/end -->` 之間，不要手改（凡例 §10）。

| 範圍 | 腳本 | 資料 |
| :--- | :--- | :--- |
| 三國人物 | `scripts/build_sanguo_mapping.py` → `scripts/build_sanguo_entries.py` | 頭像：kaodata（`img.simagame.me`）；能力值、遊戲列傳：kaodata-re 匯出；說明見 `assets/data/sanguo/README.mkdn` |
| 水滸人物 | `scripts/build_suikoden_mapping.py`、`scripts/suikoden_bios.py` → `scripts/build_suikoden_entries.py` | 頭像：kaodata（`img.simagame.me`）；能力值：`遊戲/水滸傳・天命之誓/人物資料.md`；列傳：依小說原文與維基百科整理；說明見 `assets/data/suikoden/README.mkdn` |
| 拿破崙城市 | `scripts/build_lempe_city_maps.py` | 大地圖與戰場地圖：famicom-re（`assets/maps/lempe/`） |
| 拿破崙人物索引 | `scripts/build_lempe_person_index.py` | 各人物條目的基本資料與遊戲 ID |

部分列傳先由語言模型依原文與維基百科整理成草稿，經人工審核後才上站。
