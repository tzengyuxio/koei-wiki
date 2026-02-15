# 人物百科條目檢視日誌 (拿破崙時代)

此文件紀錄了 `人物/拿破崙時代/` 目錄下條目的潛在問題，供日後人工檢視。

## 1. 重複人物 (Duplicate Entries)
這類條目指向同一個歷史人物，可能因為遊戲中不同劇本、不同譯名或 ID 導致重複。

| 歷史人物 | 相關檔案 | 備註 |
| :--- | :--- | :--- |
| 特佩萊納的阿里帕夏 | `阿里.md` (ID 194), `蒂普連.md` (ID 192) | 阿里帕夏通常指 Ioannina 之獅。 |
| 盧多維科·馬寧 | `曼寧.md` (ID 231), `羅多維可.md` (ID 228) | 威尼斯末代總督。 |
| 安德烈·伊萬諾維奇·戈爾恰科夫 | `戈雷謝可夫.md` (ID 100), `奇恰可夫.md` (ID 109) | 奇恰可夫內文標註為待考證，可能與 ID 100 重複。 |

## 2. 邏輯或資料疑慮
| 檔案 | 類型 | 疑慮描述 |
| :--- | :--- | :--- |
| `奇恰可夫.md` | 待考證 | 列傳首行標註為「（待考證）」。 |
| `寇爾.md` | 國籍矛盾 | 國籍標註為「西班牙」，但列傳描述其為「希臘學者/現代希臘文學奠基人」。 |
| `維多利亞.md` | 時代錯置 | 女王於 1819 年才出生，在拿破崙時代背景下屬於超時空角色。 |

## 3. 維基連結失效 (Wikipedia Links Broken)
以下條目的 `References` 區塊中，中文維基百科連結為 `nan`，需要人工修復：

- 丹都羅、伊凡塔多、伊匹希莫司、伯恩斯多佛、伯雷德、佛吉爾、儒瑾、克利斯坦、克拉蒙、克萊斯特、克萊茲、凡莫敦、凱敏斯基、卡巴庫爾、卡拉西歐羅、卡斯塔那司、吉納德、呂歇爾、博利厄、博恩、圖柴可夫、基瑞邁迪、塞巴斯蒂尼、塞納爾蒙、墨勃格、夏斯、多朗什、奇恰可夫、奧古斯特、尤根、尼維洛斯基、巴拉肖夫、巴紹特、布代、布萊克、布霍布登、席勒、庫利塔、庫寇、庫斯塔、庫泰卓夫、波謝、波那契、洛巴諾夫、潘森彼、珂里、瑞凡、瑞蓋司、甫傑茲、畢瑞福德、比沙洛、比藍特、沙伯龍尼、艾克頓、艾布奎克、艾普西蘭特、芮騰、范德魯、荷根多、西爾、詹森、貝利加德、貝林格、雷尼埃、雷耶、霍夫頓、霍恩洛厄、馬什、魏尼克、魯德維格、魯索、麥克唐納、麥克。

## 4. 遊戲頭像整合注意事項

- `布律納.md`（Guillaume Brune）不在遊戲 255 人名單中，無對應遊戲頭像，placeholder 未替換。
- `蘇爾特.md` 的遊戲中文名實為「史考得」（ID=17），已依 `顏` 欄位正確對應為 `LEMPE_DOS_F0017.png`。
- 以下 12 個條目無歷史肖像畫（`/assets/portraits/` 中無對應 jpg），僅有遊戲頭像：佛蘭特、卡爾十三世、卡西勒布、史考得、威瑪、巴拉肖夫、庫利塔、康斯坦丁、查理斯、洛巴諾夫、維特根施泰因、馬斯塔法四世。

## 5. 歷史肖像缺圖（Wikipedia/Wikimedia Commons 均無可用圖片）

以下 9 個條目的歷史肖像 jpg 在 md 中有引用但檔案不存在，且在 Wikipedia 及 Wikimedia Commons 上找不到可用肖像畫，需人工尋找或移除引用：

| 條目 | 缺少的檔案 | 人物原名 |
| :--- | :--- | :--- |
| `克利斯坦.md` | werner_hosewinckel_christie.jpg | Werner Hosewinckel Christie |
| `卡巴庫爾.md` | kabakc_mustafa.jpg | Kabakçı Mustafa |
| `希爾曼.md` | johann_adolf_von_thielmann.jpg | Johann Adolf von Thielmann |
| `拉姆齊.md` | norman_ramsay.jpg | Norman Ramsay |
| `沙伯龍尼.md` | gian_galeazzo_serbelloni.jpg | Gian Galeazzo Serbelloni |
| `波謝.md` | henry_percy.jpg | Henry Percy |
| `瑞凡.md` | jean_francois_leval.jpg | Jean François Leval |
| `魯索.md` | vincenzo_russo.jpg | Vincenzo Russo |
| `麥克唐納.md` | james_macdonell.jpg | James Macdonell |

---
*最後更新日期：2026-02-16*
