# merge_kgl.py
import os
import re

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.path.join(script_dir, "output")
    out_file_path = os.path.join(script_dir, "gd.kgl")

    if not os.path.isdir(output_root):
        print(f"错误：找不到目录 {output_root}")
        return

    # 收集所有<File>节点内容
    file_entries = []
    # 正则匹配 <File> 整块内容，DOTALL让.匹配换行
    pattern = re.compile(r"<File>.*?</File>", re.DOTALL)

    for root, _, files in os.walk(output_root):
        for fname in files:
            if fname.lower().endswith(".kgl"):
                full_path = os.path.join(root, fname)
                print(f"正在读取：{full_path}")
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    matches = pattern.findall(content)
                    file_entries.extend(matches)
                except Exception as e:
                    print(f"读取失败 {full_path} -> {e}")

    # 组装最终xml
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
    # 你可以自己修改ListName
    list_open = '<List ListName="欧洲榜 TOP100">\n'
    list_close = '\n</List>'

    final_content = xml_header + list_open + "\n".join(file_entries) + list_close

    with open(out_file_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"\n合并完成！一共收集 {len(file_entries)} 条File记录")
    print(f"输出文件：{out_file_path}")

if __name__ == "__main__":
    main()
