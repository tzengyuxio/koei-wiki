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

## 發布方式

- 站台是 Wiki.js 2.x，和本 repo 的 `main` **雙向 git 同步**：push 到 `main` 就會上線；在網頁上編輯也會 commit 回 repo，動手前先 `git pull`。
- `.md` 都會被匯入成頁面。不想上站的文件用 `.mkdn`（凡例、決策紀錄、模板、資料說明），或在 front matter 寫 `published: false`。
- 改名或刪除 `.md` 不會自動刪掉站上的頁面，要到後台手動刪除（會出現 `pathspec ... did not match` 錯誤，可忽略）。
- 站台 CSS 的正本是 `assets/wikijs/theme.css`，貼在後台「管理 → 主題 → Code Injection → CSS Override」。條目只寫 `kw-*` class，不寫 `style`。

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
| 水滸人物 | `scripts/build_suikoden_mapping.py`、`scripts/suikoden_bios.py` | 對照表與列傳草稿；說明見 `assets/data/suikoden/README.mkdn` |
| 拿破崙城市 | `scripts/build_lempe_city_maps.py` | 大地圖與戰場地圖：famicom-re（`assets/maps/lempe/`） |

列傳草稿由 hikari 上的 Qwen 依原文撰寫，須人工審核後才上站。
