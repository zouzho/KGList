"""酷狗音乐歌单文本格式生成器。

字段顺序、分隔符、多歌手连接符、编码与行尾格式全部来自 config/format.yaml，
格式调整不改动数据处理逻辑。
"""

from __future__ import annotations

from typing import Any, Iterable

from pipeline.aggregate import PlaylistItem


def _field_value(item: PlaylistItem, field: str, fmt: dict[str, Any]) -> str:
    if field == "title":
        return item.title
    if field == "artist":
        return str(fmt.get("artist_separator") or "/").join(item.artists)
    if field == "rank":
        return str(item.rank)
    return ""


def render(items: Iterable[PlaylistItem], fmt: dict[str, Any]) -> str:
    """把歌单条目渲染为酷狗歌单文本内容。"""

    separator = str(fmt.get("separator") or " - ")
    prefix_template = str(fmt.get("line_prefix") or "")
    fields = list(fmt.get("field_order") or ["title", "artist"])

    lines: list[str] = []
    for item in items:
        prefix = prefix_template.format(rank=item.rank) if prefix_template else ""
        values = [value for value in (_field_value(item, field, fmt) for field in fields) if value]
        lines.append(f"{prefix}{separator.join(values)}")

    blocks: list[str] = []
    header = str(fmt.get("header") or "")
    if header:
        blocks.append(header)
    blocks.extend(lines)
    footer = str(fmt.get("footer") or "")
    if footer:
        blocks.append(footer)

    line_ending = str(fmt.get("line_ending") or "\n")
    return line_ending.join(blocks) + line_ending


def output_filename(slug: str, limit: int, fmt: dict[str, Any]) -> str:
    """按命名规范生成歌单文件名。"""

    pattern = str(fmt.get("filename_pattern") or "{slug}_top{limit}")
    extension = str(fmt.get("extension") or ".txt")
    return pattern.format(slug=slug, limit=limit) + extension
