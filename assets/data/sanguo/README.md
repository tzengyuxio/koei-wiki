# 三國人物資料

| 檔案 | 內容 | 怎麼產生 |
| :--- | :--- | :--- |
| `sanguo-bios.jsonl` | 列傳草稿，一行一人：`name`、`courtesy`、`faction`、`bio`、`refs` | 先前批次撰寫 |
| `persons-mapping.csv` | wiki 條目 ↔ 各代遊戲內人物 ID，一列一個條目、一欄一個資料集 | `scripts/build_sanguo_mapping.py` |
| `persons-unmatched.csv` | 遊戲裡有、但沒有對上 wiki 條目的人物，供人工檢查 | 同上 |
| `persons-overrides.csv` | 人工指定的對應（同名人物、特殊寫法），欄位 `dataset,id,wiki名,備註`；`wiki名` 填 `-` 表示不是三國人物、不對應 | 手動維護 |
| `persons-new.csv` | 還沒有 wiki 檔案的三國人物，欄位 `wiki名,勢力,出典,備註`；script 會把它們當成條目一起對應 | 手動維護 |
| `persons-excluded.csv` | 刻意不對應的遊戲人物（其他時代、遊戲原創、泛稱、神仙），欄位 `dataset,id,類別,備註` | 手動維護 |

## persons-mapping.csv

- 欄位：`wiki名`（`人物/三國/` 下的檔名，不含 `.md`）、`勢力`（取自 `sanguo-bios.jsonl`），之後每一欄是一個 kaodata 資料集，值為遊戲內人物 ID；同一資料集對到多個 ID 時以 `|` 分隔，沒登場留空。
- 資料集順序：正傳 14 代（`san1-pc98` … `san14pk-win`，依 kaodata `docs/mainline.md`），接著是光榮其他作品（`san1-fc`、`san2-fc`、`san1-sfc`、`san2-sfc`、`san1-x68`、`eiketsu-pc98`）。
- 頭像網址：`https://img.simagame.me/kaodata/faces/<資料集>/<ID>.png`。
- 不要手改這個檔案；要修正對應就改 `persons-overrides.csv` 或 script 裡的別名表，再重跑。

## 比對方式

kaodata 的 `index.json`（`https://img.simagame.me/kaodata/faces/<資料集>/index.json`）提供各代人物的 `name`（遊戲原文，日文版為新字體）、`nameZh`（三13、三14）、`nameHistorical`。script 依序：

1. 取 `nameHistorical`，沒有就取 `nameZh`，再沒有就取 `name`。
2. 新字體轉繁體（如 関→關、呉→吳），套用整名別名（如 許子将→許劭、梁剛→梁綱）。
3. 異體字只在比對時統一（如 脩／修、毗／毘、橋／喬），輸出仍用 wiki 條目名。
4. 對上唯一一個 wiki 條目就寫入；對上多個（同名人物）或對不上，寫進 `persons-unmatched.csv`。

`index.json` 快取在 `~/.cache/koei-wiki/kaodata-faces/`，加 `--refresh` 重新下載。

## 遊戲內列傳（不進版控）

kaodata-re 從繁中版遊戲抽出的武將列傳，放在 `~/works/kaodata-re/export/koei-wiki/<資料集>.jsonl`，只在本機，因為內容是遊戲文字。寫列傳時當作資料來源之一。

- 格式：一行一段，`{"dataset","id","name","lang":"zh-Hant","kind","text"}`。`kind` 是 `簡介`、`演義`、`史實` 或 `單段`；遊戲寫「無記述」的段不輸出。
- 資料集：`san4pk-dos`（454 人）、`san5pk-dos`（500）、`san6pk-win`（520）、`san13pk-win`（821）、`san14pk-win`（1001）。三4、三5 是單段，三13、三14 大多分簡介、演義、史實三段。
- 對應：用 `id` 對 `persons-mapping.csv`。三4、三5 的 dos 版 ID 和 mapping 欄位 `san4pk-pc98`、`san5pk-pc98` 相同，已逐一比對過。沒對上的只有被排除的人物：三4、三5 的左賢王，三13 的 14 位古武將，三14 的英布。
- 重產：在 kaodata-re 的 `dekoei/` 下執行 `../.venv/bin/python dekoei.py biography <資料集> --game-dir ../games/<資料集> --out ../export/koei-wiki/<資料集>.jsonl`。
- 注意：三4、三5 的原文是光榮台灣內碼，三4 的「．」已改成「。」；三13、三14 的外字是依上下文判斷的。
