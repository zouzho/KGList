# merge_kgl.py
import os
import re
import time
import json
import requests
from urllib.parse import quote

# -------------------------- 配置区 --------------------------
# 搜歌接口（第三方逆向接口，不稳定，失效需要更换）
SEARCH_API = "https://api.lolimi.cn/API/kgmusic/search.php"
# 请求间隔，防止限流，单位秒
REQ_DELAY = 1.2
# 缓存文件，避免重复搜索同一首歌
CACHE_FILE = "hash_cache.json"
# 输出歌单名称
LIST_NAME = "欧洲榜 TOP100"
# ------------------------------------------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_kugou_hash(song_name: str, cache: dict):
    """根据歌名搜索酷狗，返回filehash；找不到返回 None"""
    if song_name in cache:
        return cache[song_name]

    try:
        resp = requests.get(SEARCH_API, params={"name": song_name}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 200 and data.get("data"):
            # 取第一条结果的hash
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

def parse_file_block(raw_block: str):
    """
    解析单条 <File>...</File> 块，提取各个字段
    返回字典：{FilePath, FileSize, Duration, Hash, Lyric, BitRate, MediaFileType, FileName}
    """
    pat = re.compile(r"<(?P<tag>.*?)>(?P<val>.*?)</(?P=tag)>", re.DOTALL)
    fields = {}
    for m in pat.finditer(raw_block):
        tag = m.group("tag")
        val = m.group("val").strip()
        fields[tag] = val
    return fields

def build_file_xml(item: dict) -> str:
    """把字段字典重新组装成 <File> xml片段"""
    return (
        "<File>"
        f"<FilePath>{item['FilePath']}</FilePath>"
        f"<FileSize>{item['FileSize']}</FileSize>"
        f"<Duration>{item['Duration']}</Duration>"
        f"<Hash>{item['Hash']}</Hash>"
        f"<Lyric>{item['Lyric']}</Lyric>"
        f"<BitRate>{item['BitRate']}</BitRate>"
        f"<MediaFileType>{item['MediaFileType']}</MediaFileType>"
        f"<FileName>{item['FileName']}</FileName>"
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

    file_blocks = []
    pattern_file = re.compile(r"<File>.*?</File>", re.DOTALL)

    for root, _, files in os.walk(output_root):
        for fname in files:
            if fname.lower().endswith(".kgl"):
                full_path = os.path.join(root, fname)
                print(f"\n读取文件：{full_path}")
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    blocks = pattern_file.findall(content)
                    for blk in blocks:
                        info = parse_file_block(blk)
                        song_name = info.get("FileName", "")
                        if not song_name:
                            print("⚠️ 本条无FileName，跳过")
                            continue
                        # 搜索hash
                        h = get_kugou_hash(song_name, cache)
                        if h:
                            info["Hash"] = h
                            print(f"✅ {song_name} -> {h}")
                        else:
                            info["Hash"] = "0"
                            print(f"❌ {song_name} 未搜到hash，保留0")
                        file_blocks.append(build_file_xml(info))
                except Exception as e:
                    print(f"读取失败 {full_path} -> {e}")

    # 保存缓存
    save_cache(cache)

    # 组装最终xml
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    list_open = f'<List ListName="{LIST_NAME}">\n'
    list_close = '\n</List>'
    final = xml_header + list_open + "\n".join(file_blocks) + list_close

    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(final)

    print(f"\n✅ 合并完成！一共 {len(file_blocks)} 条歌曲记录")
    print(f"输出：{out_file_path}")

if __name__ == "__main__":
    main()
