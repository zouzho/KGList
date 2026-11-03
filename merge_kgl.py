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
            if fname.lower().endswith(".kgl"):
                full_path = os.path.join(root, fname)
                print(f"\n读取文件：{full_path}")
                file_items = parse_kgl_xml(full_path)
                for info in file_items:
                    song_name = info.get("FileName", "").strip()
                    
                    if not song_name:
                        print("⚠️ 本条无FileName，跳过")
                        continue                    
                    
                    # 按照 《歌名》-- 歌手名 格式拼接
                    arr = song_name.strip("-")

                    line = f"《{arr[0]}》-- {arr[1]}"
                    song_lines.append(line)

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
        .sc-btn{display:inline-block;padding:14px 28px;background:#e94560;color:#fff;border:none;border-radius:10px;font-weight:bold;font-size:17px;cursor:pointer;transition:0.2s;margin:5px}
        .sc-btn:hover{background:#c81e45}
        .sc-btn:disabled{background:#555;cursor:not-allowed}
    </style>
</head>
<body>
    <h1>🎵 歌单列表</h1>
    <button class="sc-btn" onclick="captureScreenshot()">📸 一键截图保存</button>
    <ul>
        {list_items_html}
    </ul>
            <script>
        async function captureScreenshot() {
            const btn = document.querySelector('.sc-btn');
            const captureArea = document.getElementById('capture-area');
            
            btn.innerText = '⏳ 正在生成截图...';
            btn.disabled = true;

            try {
                const canvas = await html2canvas(captureArea, {
                    useCORS: true, // 允许跨域图片（如果有）
                    scale: 2,      // 提高清晰度，按2倍像素渲染
                    backgroundColor: '#16213e' // 指定背景色，防止透明背景
                });

                const imgDataUrl = canvas.toDataURL('image/png');

                const link = document.createElement('a');
                link.href = imgDataUrl;
                link.download = 'KGL歌单截图_' + new Date().getTime() + '.png';
                
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

            } catch (error) {
                console.error('截图失败:', error);
                alert('截图生成失败，请重试！');
            } finally {
                btn.innerText = '📸 一键截图保存';
                btn.disabled = false;
            }
        }
        </script>
</body>
</html>"""

    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ 合并完成！一共 {len(song_lines)} 条歌曲记录")
    print(f"输出：{out_file_path}")

if __name__ == "__main__":
    main()
