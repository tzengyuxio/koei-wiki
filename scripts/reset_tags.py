import os
import re

def reset_tags(directory):
    print(f"開始處理目錄: {directory}")
    count = 0
    # 匹配 YAML frontmatter 中的 tags 欄位，不論是單行 [ ] 格式還是多行格式
    # 模式說明：匹配 tags: 後面跟著直到換行的所有內容
    pattern = re.compile(r'^tags:.*$', re.MULTILINE)

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md") and file != "home.md":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 檢查是否存在 tags 欄位
                    if pattern.search(content):
                        # 替換為單純的 tags: lempe
                        new_content = pattern.sub("tags: lempe", content)
                        
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        count += 1
                except Exception as e:
                    print(f"處理 {file} 時發生錯誤: {e}")
                    
    print(f"處理完成，共修改 {count} 個檔案。")

if __name__ == "__main__":
    reset_tags("人物/拿破崙時代")
