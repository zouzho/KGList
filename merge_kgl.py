# merge_kgl.py
import os
import time
import json
import requests
import xml.etree.ElementTree as ET
import re
import sys
import shutil
from pathlib import Path

# -------------------------- 配置区 --------------------------
SEARCH_API = "https://api.lolimi.cn/API/kgmusic/search.php"
REQ_DELAY = 1.2
CACHE_FILE = "hash_cache.json"
# ------------------------------------------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def parse_kgl_xml(file_path):
    """读取单个kgl，提取所有File子节点，返回字段字典列表"""
    items = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        root = ET.fromstring(raw)
        for file_node in root.findall("File"):
            item = {}
            for child in file_node:
                item[child.tag] = child.text if child.text is not None else ""
            items.append(item)
    except Exception as e:
        print(f"XML解析失败 {file_path} -> {e}")
    return items

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.path.join(script_dir, "output")
    # 输出同级别的 gd.html 文件
    out_file_path = os.path.join(script_dir, "gd.html")
    cache = load_cache()

    if not os.path.isdir(output_root):
        print(f"错误：找不到目录 {output_root}")
        return

    song_lines = []

    for root, _, files in os.walk(output_root):
        for fname in files:
            if fname.lower().endswith(".txt"):
                full_path = os.path.join(root, fname)
                print(f"\n读取文件：{full_path}")
                with open(full_path, "r", encoding="utf-8") as f:
                    cnt = 0
                    for line in f:
                        if cnt > 100:
                            print("⚠️ 100条以外的歌曲，跳过")
                            continue
                        line = line.strip()
                        
                        if not line:
                            print("⚠️ 本条无FileName，跳过")
                            continue                 
                        
                        # 按照 《歌名》-- 歌手名 格式拼接
                        parts  = line.split(" - ", 1)
                        if len(parts) == 2:
                            A = parts[0]
                            B = parts[1]

                            line = f"《{A}》{B}"        
                            cnt += 1
                            print(f"{line} -> cnt = {cnt}")
                            song_lines.append(line)
                        else:
                            print(f"⚠️ 本条格式有误，跳过：{line}")
                        
    save_cache(cache)

    html = out_file_path.read_text(encoding="utf-8")

    # 匹配 <ul id='mylist' ...> ... </ul>，兼容单引号/双引号/带其他属性/多行内容
    UL_PATTERN = re.compile(
        r"(<ul\s+id\s*=\s*['\"]mylist['\"][^>]*>)(.*?)(</ul>)",
        re.DOTALL | re.IGNORECASE,
    )

    UL_PATTERN.sub(lambda m: m.group(1) + m.group(3), html, count=1) # 1. 清空原有子项

    item_songs = "\n".join(f"    <li>{song}</li>" for song in song_lines)
    html = UL_PATTERN.sub(lambda m: m.group(1) + item_songs + m.group(3), html, count=1) # 2. 添加新子项

    out_file_path.write_text(html, encoding="utf-8")
    print(f"\n✅ 合并完成！一共 {len(song_lines)} 条歌曲记录")
    print(f"输出：{out_file_path}")

if __name__ == "__main__":
    main()
