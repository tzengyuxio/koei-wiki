import os
import re

def format_image_captions(directory):
    print(f"開始處理目錄: {directory}")
    count = 0
    # 匹配圖片語法後緊跟著斜體描述文字的模式
    # pattern 捕獲圖片行和描述行
    pattern = re.compile(r'^(!\[.*?\]\(.*?\))\n(\*.*?\*)', re.MULTILINE)

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if pattern.search(content):
                        new_content = pattern.sub(r'\1\n\n\2', content)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        count += 1
                except Exception as e:
                    print(f"處理 {file} 時發生錯誤: {e}")
                    
    print(f"處理完成，共修改 {count} 個檔案。")

if __name__ == "__main__":
    format_image_captions("人物/拿破崙時代")
