import os
import re

def cleanup():
    # 遍歷所有 .md 檔案
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                
                # 跳過腳本目錄與內部改善報告
                if 'scripts' in file_path or 'ADSENSE_IMPROVEMENT.md' in file_path:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # 1. 檢查是否為空殼條目 (Your content here)
                    if "Your content here" in content:
                        if 'published: true' in content:
                            content = content.replace('published: true', 'published: false')
                        elif 'published: false' not in content:
                            # 如果沒有 published 標記且有 front matter，補上
                            if content.startswith('---'):
                                content = content.replace('---\n', '---\npublished: false\n', 1)
                    
                    # 2. 移除 "(施工中)" 標記
                    content = content.replace('(施工中)', '')
                    content = content.replace('（施工中）', '')
                    
                    # 如果內容有變動，寫回檔案
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        # 僅列印部分結果以節省 token
                except Exception as e:
                    pass

if __name__ == "__main__":
    cleanup()
    print("Cleanup completed.")
