import pandas as pd
import re
import os

def merge_data():
    mapping_path = "assets/data/lempereur/lempe-persons-mapping.csv"
    md_path = "遊戲/拿破崙/人物資料.md"
    output_path = "assets/data/lempereur/lempe-persons-full.csv"

    # 1. 讀取 CSV
    mapping_df = pd.read_csv(mapping_path)
    
    # 2. 讀取 Markdown 並解析表格
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    rows = []
    start_parsing = False
    for line in lines:
        line = line.strip()
        if "|ID |" in line and "姓名" in line:
            start_parsing = True
            continue
        if start_parsing and "|--:|" in line:
            continue
        if start_parsing and line.startswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if cols:
                rows.append(cols)
        elif start_parsing and not line.strip():
            # 遇到空行停止解析表格
            break
            
    stats_df = pd.DataFrame(rows, columns=[
        "ID", "姓名", "中文版", "英文版", "國家", "顏", 
        "政治", "財政", "補給", "建設", "指揮", 
        "步兵", "騎兵", "砲兵", "冷靜", "勇敢", "魅力", "幸運"
    ])
    
    # 確保 ID 為整數以便合併
    mapping_df['編號'] = mapping_df['編號'].astype(int)
    stats_df['ID'] = stats_df['ID'].astype(int)
    
    # 3. 合併
    full_df = pd.merge(mapping_df, stats_df, left_on="編號", right_on="ID", how="left")
    
    # 4. 儲存
    full_df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"成功整合檔案至: {output_path}")

if __name__ == "__main__":
    merge_data()
