import os
import json
import sys
import subprocess
import re
import unicodedata
from datetime import datetime

TEMPLATE_PATH = "assets/person_template_v2.md"
PORTRAIT_DIR = "assets/portraits"

def normalize_filename(name):
    """將人名轉換為符合專案慣例的 snake_case 檔名"""
    name = unicodedata.normalize('NFD', name)
    name = "".join([c for c in name if not unicodedata.combining(c)])
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    return name.strip('_')

def get_wiki_image_url(en_wiki_url):
    if not en_wiki_url or "wikipedia.org" not in en_wiki_url:
        return None
    try:
        cmd = f"curl -sL \"{en_wiki_url}\" | grep 'og:image' | sed -n 's/.*content=\"\\([^\"]*\\)\".*/\\1/p' | head -n 1"
        url = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        return url if url.startswith("http") else None
    except Exception:
        return None

def download_image(url, target_path):
    if os.path.exists(target_path):
        return True
    try:
        subprocess.run(["curl", "-sL", "-o", target_path, url], check=True)
        return True
    except Exception:
        return False

def generate_person(data):
    # 1. 處理肖像
    real_name_orig = data.get("name_orig", "")
    portrait_base = normalize_filename(real_name_orig)
    portrait_filename = f"{portrait_base}.jpg"
    portrait_path = os.path.join(PORTRAIT_DIR, portrait_filename)
    
    # 只有在圖片不存在時才嘗試抓取
    if not os.path.exists(portrait_path):
        image_url = get_wiki_image_url(data.get("wiki_en", ""))
        if image_url:
            download_image(image_url, portrait_path)

    # 2. 準備替換資料
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    tags = data.get("tags", [])
    tag_list_str = "\n".join([f"  - {t}" for t in tags])
    
    replacements = {
        "{遊戲內中文名}": data.get("game_zh_name", ""),
        "{人物描述}": data.get("desc", ""),
        "{YYYY-MM-DDTHH:MM:SS.000Z}": now,
        "{標籤列表}": tag_list_str,
        "{真實中文譯名}": data.get("name_zh", ""),
        "{真實原名}": real_name_orig,
        "{遊戲日文名}": data.get("game_ja", ""),
        "{遊戲英文名}": data.get("game_en", ""),
        "{遊戲中文名}": data.get("game_zh_name", ""),
        "{國籍}": data.get("country", ""),
        "{ID}": str(data.get("id", "")),
        "{政治}": str(data.get("pol", "")),
        "{財政}": str(data.get("eco", "")),
        "{補給}": str(data.get("sup", "")),
        "{建設}": str(data.get("con", "")),
        "{指揮}": str(data.get("lea", "")),
        "{步兵}": str(data.get("inf", "")),
        "{騎兵}": str(data.get("cav", "")),
        "{砲兵}": str(data.get("art", "")),
        "{冷靜}": str(data.get("calm", "")),
        "{勇敢}": str(data.get("brave", "")),
        "{魅力}": str(data.get("cha", "")),
        "{幸運}": str(data.get("luc", "")),
        "{肖像路徑}": f"/assets/portraits/{portrait_filename}",
        "{人物列傳}": data.get("bio", ""),
        "{中文維基}": data.get("wiki", ""),
        "{英文維基}": data.get("wiki_en", ""),
    }

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    for k, v in replacements.items():
        content = content.replace(k, str(v))

    # 3. 儲存檔案 (使用遊戲內中文名作為檔名)
    target_dir = os.path.join("人物", data.get("category", "其他"))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_name = f"{data.get('game_zh_name')}.md"
    file_path = os.path.join(target_dir, file_name)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"成功建立: {file_path}")

if __name__ == "__main__":
    try:
        data = json.loads(sys.argv[1])
        generate_person(data)
    except Exception as e:
        print(f"錯誤: {e}")
