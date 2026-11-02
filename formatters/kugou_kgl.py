"""酷狗音乐歌单文件（.kgl）生成器。

酷狗 .kgl 是 XML 结构的歌单文件，客户端在列表空白处右键「导入列表」即可导入：

    <?xml version="1.0" encoding="windows-1252"?>
    <List ListName="热歌榜 TOP100">
    <File><FilePath>E:\\</FilePath>...<FileName>歌手 - 歌名</FileName></File>
    ...
    </List>

原生导出使用本地 ANSI 编码（中文即 GBK）并在声明行写 windows-1252，
因此默认沿用该组合；字段集合、FileName 写法、编码与行尾均可在
config/format.yaml 的 kugou_kgl 段调整，格式调整不改动数据处理逻辑。
"""

from __future__ import annotations

import html
from typing import Any, Iterable

from pipeline.aggregate import PlaylistItem

DEFAULT_XML_DECLARATION = '<?xml version="1.0" encoding="windows-1252"?>'
DEFAULT_FILE_TEMPLATE = (
    "<File><FilePath>E:\\</FilePath><FileSize>0</FileSize><Duration>0</Duration>"
    "<Hash>0</Hash><Lyric>E:\\</Lyric><BitRate>192</BitRate><MediaFileType>0</MediaFileType>"
    "<FileName>{filename}</FileName></File>"
)


def _escape(value: str) -> str:
    """XML 文本转义（& < > 等）。"""

    return html.escape(value or "", quote=False)


def build_filename(item: PlaylistItem, fmt: dict[str, Any]) -> str:
    """生成 FileName 字段内容，默认「歌手 - 歌名」。"""

    template = str(fmt.get("filename_template") or "{artist} - {title}")
    artist = str(fmt.get("artist_separator") or "/").join(item.artists)
    return template.format(artist=artist, title=item.title, rank=item.rank).strip()


def render(items: Iterable[PlaylistItem], fmt: dict[str, Any]) -> str:
    """把歌单条目渲染为酷狗 .kgl 文件内容。"""

    items = list(items)
    line_ending = str(fmt.get("line_ending") or "\r\n")
    declaration = str(fmt.get("xml_declaration") or DEFAULT_XML_DECLARATION)
    list_name = _escape(
        str(fmt.get("list_name_template") or "{label}").format(
            label=fmt.get("_label") or "",
            limit=fmt.get("_limit") or "",
            week=fmt.get("_week") or "",
        )
    )

    blocks = [declaration, f'<List ListName="{list_name}">']
    for item in items:
        filename = _escape(build_filename(item, fmt))
        if fmt.get("include_full_fields", True):
            template = str(fmt.get("file_template") or DEFAULT_FILE_TEMPLATE)
            blocks.append(template.format(filename=filename))
        else:
            blocks.append(f"<File><FileName>{filename}</FileName></File>")
    blocks.append("</List>")
    return line_ending.join(blocks) + line_ending


def output_filename(slug: str, limit: int, fmt: dict[str, Any]) -> str:
    """按命名规范生成歌单文件名。"""

    pattern = str(fmt.get("filename_pattern") or "{slug}_top{limit}")
    extension = str(fmt.get("extension") or ".kgl")
    return pattern.format(slug=slug, limit=limit) + extension
