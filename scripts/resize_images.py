#!/usr/bin/env python3
import os
import sys
import subprocess

def resize_images(folder_path):
    # 支援的圖片副檔名
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.tiff')
    
    if not os.path.isdir(folder_path):
        print(f"錯誤: {folder_path} 不是有效的資料夾。")
        return

    print(f"開始處理資料夾: {folder_path}")
    
    count = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(valid_extensions):
                file_path = os.path.join(root, file)
                
                # magick 指令說明:
                # -resize "1280x1280>" : 
                #   1. 維持比例
                #   2. 如果寬或高大於 1280px，則縮放至 1280px
                #   3. 如果都小於 1280px，則不執行縮放 (由 > 符號控制)
                try:
                    # 使用 subprocess 呼叫系統的 ImageMagick
                    cmd = ["magick", file_path, "-resize", "1280x1280>", file_path]
                    subprocess.run(cmd, check=True, capture_output=True)
                    count += 1
                except subprocess.CalledProcessError as e:
                    print(f"處理失敗: {file_path}, 錯誤: {e.stderr.decode().strip()}")

    print(f"處理完成！共檢查/處理 {count} 張圖片。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/resize_images.py <資料夾路徑>")
    else:
        target_dir = sys.argv[1]
        resize_images(target_dir)
