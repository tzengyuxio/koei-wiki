import os
import re

def format_tags(directory):
    print(f"開始處理目錄: {directory}")
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md") and file != "home.md":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 匹配 YAML frontmatter
                    match = re.search(r'^---(.*?)---', content, re.DOTALL | re.MULTILINE)
                    if not match:
                        continue
                        
                    yaml_content = match.group(1)
                    
                    # 匹配多行 tags 塊
                    tags_pattern = r'tags:\s*\n((?:\s*-.*?\n)+)'
                    tags_match = re.search(tags_pattern, yaml_content)
                    
                    if tags_match:
                        full_tags_block = tags_match.group(0)
                        tags_lines = tags_match.group(1)
                        
                        # 提取標籤並去重
                        raw_tags = re.findall(r'-\s*(.*)', tags_lines)
                        unique_tags = []
                        seen = set()
                        for t in raw_tags:
                            t = t.strip()
                            if t and t not in seen:
                                unique_tags.append(t)
                                seen.add(t)
                        
                        # 格式化為單行
                        new_tags_line = f"tags: [{', '.join(unique_tags)}]\n"
                        
                        new_yaml = yaml_content.replace(full_tags_block, new_tags_line)
                        new_content = content.replace(yaml_content, new_yaml)
                        
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        count += 1
                except Exception as e:
                    print(f"處理 {file} 時發生錯誤: {e}")
                    
    print(f"處理完成，共修改 {count} 個檔案。")

if __name__ == "__main__":
    format_tags("人物/拿破崙時代")
