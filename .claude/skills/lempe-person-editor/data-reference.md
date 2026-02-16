# Data Reference

## CSV Files

All CSV files are in `assets/data/lempereur/`.

### lempe-persons-full.csv (Main mapping)

The master reference for character identification. 255 entries (ID 0-254).

| Column | Description |
|:-------|:------------|
| 編號 | Sequential index (= ID) |
| 遊戲英文名 | English localized name in game |
| 遊戲中文名 | Chinese localized name in game (**= md filename**) |
| 遊戲日文名 | Japanese katakana name in game |
| 真實原名 | Real historical name |
| 真實中文譯名 | Real name in Chinese |
| 英文Wiki | English Wikipedia URL |
| 中文Wiki | Chinese Wikipedia URL (may be `nan`) |
| 備註 | Notes (identity clues, known issues) |
| ID–幸運 | Duplicated stats columns from s1-zh |

### lempe-persons-s1-zh.csv (Scenario 1 stats)

Game stats for Scenario 1. **This is the authoritative source for the `顏` (face) column.**

| Column | Description |
|:-------|:------------|
| ID | Character index (0-254) |
| 姓名 | In-game Chinese name |
| **顏** | **Face image index** → `LEMPE_DOS_F{顏:04d}.png` |
| 政治–砲兵 | Ability ranks (A/B/C/D) |
| 冷靜 | Composure trait (冷靜/單純/blank) |
| 勇敢 | Bravery trait (勇氣/膽小/blank) |
| 魅力 | Charisma trait (魅力/blank) |
| 幸運 | Luck trait (幸運/blank) |
| 城市 | Starting city |
| 國籍 | Nationality |

### lempe-persons-s2/s3/s4-zh.csv

Stats for Scenarios 2-4. Same column structure as s1-zh.

## Japanese Database

- URL: `http://hima.que.ne.jp/simulation/lempereur.cgi`
- Pagination: `?up1=0;target=255;max=255;print=20;p=N`
- Contains detailed Japanese-language character profiles
- Hex codes 0x00-0xFE correspond to ID 0-254
- **Unstable**: Occasionally returns HTTP 500

## Image Assets

### Historical Portraits (`assets/portraits/`)

- Format: JPEG
- Naming: `{lowercase_snake_case_of_real_name}.jpg`
- Source: Wikipedia / Wikimedia Commons
- Some entries have no available historical portrait (see `review_log.md` section 5)

### Game Faces (`assets/portraits/gamefaces/`)

- Format: PNG, 64×80 pixels
- Naming: `LEMPE_DOS_F{顏:04d}.png` (0000-0259)
- Source: Extracted from DOS version of L'Empereur
- **Important**: File number = `顏` column, NOT character ID

## Unidentified Characters (15)

These characters have not been matched to real historical persons:

| ID | EN Name | ZH Name | Country |
|:---|:--------|:--------|:--------|
| 84 | Wade | 乘乘 | England |
| 89 | Nomire | 諾乘乘 | England |
| 91 | Dawson | 道乘 | England |
| 161 | Luveck | 盧乘克 | Austria |
| 172 | Cambier | 坎乘 | Holland |
| 176 | Cleves | 克萊茲 | Bavaria |
| 196 | Cherebi | 乘乘比 | Ottoman |
| 200 | Selanovitch | 乘乘維奇 | Ottoman |
| 226 | Galiani | 加里乘尼 | Italy |
| 227 | Neri | 尼乘 | Italy |
| 249 | Jansen | 詹森 | Denmark |
| 250 | Bernhard | 伯恩乘 | Denmark |
| 251 | Sweyn | 史乘 | Denmark |
| 252 | Erik | 乘乘克 | Denmark |
| 253 | Hague | 黑乘 | Denmark |
