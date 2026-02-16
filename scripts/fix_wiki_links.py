#!/usr/bin/env python3
import os
import re
import subprocess
import json
import urllib.parse
import sys

def get_zh_wiki_via_wikidata(en_title):
    # 使用 curl 呼叫維基百科 API 以獲取跨語言連結
    api_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=langlinks&titles={urllib.parse.quote(en_title)}&lllang=zh&format=json"
    try:
        cmd = ["curl", "-sL", api_url]
        result = subprocess.check_output(cmd).decode('utf-8')
        data = json.loads(result)
        pages = data.get("query", {}).get("pages", {})
        for page_id in pages:
            langlinks = pages[page_id].get("langlinks", [])
            if langlinks:
                zh_title = langlinks[0]['*']
                # 確保返回完整的 URL 並正確轉義
                return f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(zh_title.replace(' ', '_'))}"
    except Exception:
        pass
    return None

def process_files(directory):
    print(f"開始掃描目錄: {directory}")
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 尋找包含 (nan) 的維基連結
                if "(nan)" in content:
                    # 嘗試從英文維基連結提取 ID
                    en_pattern = r"\[.*? - Wikipedia\]\(https://en\.wikipedia\.org/wiki/(.*?)\)"
                    en_match = re.search(en_pattern, content)
                    
                    if en_match:
                        en_id = en_match.group(1).split("#")[0]
                        zh_link = get_zh_wiki_via_wikidata(en_id)
                        
                        if zh_link:
                            # 替換 nan
                            new_content = re.sub(r"\(nan\)", f"({zh_link})", content, count=1)
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(new_content)
                            print(f"已修復: {file} -> {zh_link}")
                            count += 1
                        else:
                            # 如果真的找不到，標記為「(無中文條目)」以避免 nan 誤導
                            new_content = re.sub(r"\(nan\)", "(無中文條目)", content, count=1)
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(new_content)
                            print(f"標記為無條目: {file}")
                            count += 1

    print(f"處理完成，共修復/更新 {count} 個檔案。")

if __name__ == "__main__":
    target_dir = "人物/拿破崙時代"
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    process_files(target_dir)
