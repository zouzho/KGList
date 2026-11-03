# merge_kgl.py
import os
import time
import json
import requests
import xml.etree.ElementTree as ET

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
                with open(full_path, "r", encoding="utf-8") as file_items:
                    for line in file_items:
                        line = line.strip()
                        print(f"{line}")

                        if not line:
                            print("⚠️ 本条无FileName，跳过")
                            continue                 
                        
                        # 按照 《歌名》-- 歌手名 格式拼接
                        parts  = line.strip(" - ")
                        print(f"{parts}")
                        if len(parts) == 2:
                            A = parts[0]
                            B = parts[1]

                            line = f"《{A}》-- {B}"
                            song_lines.append(line)
                        else:
                            print(f"⚠️ 本条格式有误，跳过：{line}")

    save_cache(cache)

    # 生成 HTML 内容
    # 将每一行转换为 <li> 标签，并使用换行符连接
    list_items_html = "\n".join([f"    <li>{line}</li>" for line in song_lines])
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>歌单列表</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 40px auto;
            max-width: 800px;
            padding: 0 20px;
        }}
        h1 {{
            text-align: center;
            color: #444;
        }}
        ul {{
            list-style-type: decimal;
            background: #fff;
            padding: 20px 40px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        li {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
            font-size: 16px;
        }}
        li:last-child {{
            border-bottom: none;
        }}
    </style>
</head>
<body>
    <h1>🎵 歌单列表</h1>
    <ul>
        {list_items_html}
    </ul>
</body>
</html>"""

    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ 合并完成！一共 {len(song_lines)} 条歌曲记录")
    print(f"输出：{out_file_path}")

if __name__ == "__main__":
    main()
