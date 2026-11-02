# merge_kgl.py
import os
import re
import time
import json
import requests
import xml.etree.ElementTree as ET

# -------------------------- 配置区 --------------------------
SEARCH_API = "https://api.lolimi.cn/API/kgmusic/search.php"
REQ_DELAY = 1.2
CACHE_FILE = "hash_cache.json"
LIST_NAME = "欧洲榜 TOP100"
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

def get_kugou_hash(song_name: str, cache: dict):
    if song_name in cache:
        return cache[song_name]

    try:
        resp = requests.get(SEARCH_API, params={"name": song_name}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 200 and data.get("data"):
            hash_val = data["data"][0]["hash"]
            cache[song_name] = hash_val
            time.sleep(REQ_DELAY)
            return hash_val
        else:
            cache[song_name] = "0"
            time.sleep(REQ_DELAY)
            return None
    except Exception as e:
        print(f"搜索【{song_name}】失败：{e}")
        cache[song_name] = "0"
        time.sleep(REQ_DELAY)
        return None

def parse_kgl_xml(file_path):
    """读取单个kgl，提取所有File子节点，返回字段字典列表"""
    items = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        # 补根节点，防止ET解析报错
        root = ET.fromstring(raw)
        for file_node in root.findall("File"):
            item = {}
            for child in file_node:
                item[child.tag] = child.text if child.text is not None else ""
            items.append(item)
    except Exception as e:
        print(f"XML解析失败 {file_path} -> {e}")
    return items

def build_file_xml(item: dict) -> str:
    return (
        "<File>"
        f"<FilePath>{item.get('FilePath','')}</FilePath>"
        f"<FileSize>{item.get('FileSize','0')}</FileSize>"
        f"<Duration>{item.get('Duration','0')}</Duration>"
        f"<Hash>{item.get('Hash','0')}</Hash>"
        f"<Lyric>{item.get('Lyric','')}</Lyric>"
        f"<BitRate>{item.get('BitRate','192')}</BitRate>"
        f"<MediaFileType>{item.get('MediaFileType','0')}</MediaFileType>"
        f"<FileName>{item.get('FileName','')}</FileName>"
        "</File>"
    )

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.path.join(script_dir, "output")
    out_file_path = os.path.join(script_dir, "gd.kgl")
    cache = load_cache()

    if not os.path.isdir(output_root):
        print(f"错误：找不到目录 {output_root}")
        return

    all_file_items = []

    for root, _, files in os.walk(output_root):
        for fname in files:
            if fname.lower().endswith(".kgl"):
                full_path = os.path.join(root, fname)
                print(f"\n读取文件：{full_path}")
                file_items = parse_kgl_xml(full_path)
                for info in file_items:
                    song_name = info.get("FileName", "").strip()
                    if not song_name:
                        print("⚠️ 本条无FileName，跳过")
                        continue
                    h = get_kugou_hash(song_name, cache)
                    if h:
                        info["Hash"] = h
                        print(f"✅ {song_name} -> {h}")
                    else:
                        info["Hash"] = "0"
                        print(f"❌ {song_name} 未搜到hash，保留0")
                    all_file_items.append(build_file_xml(info))

    save_cache(cache)

    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    list_open = f'<List ListName="{LIST_NAME}">\n'
    list_close = '\n</List>'
    final = xml_header + list_open + "\n".join(all_file_items) + list_close

    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(final)

    print(f"\n✅ 合并完成！一共 {len(all_file_items)} 条歌曲记录")
    print(f"输出：{out_file_path}")

if __name__ == "__main__":
    main()
