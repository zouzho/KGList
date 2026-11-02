"""歌单文件格式注册表：按配置选择输出格式。

每个格式化模块统一暴露：
    render(items, fmt) -> str                歌单文件内容
    output_filename(slug, limit, fmt) -> str 歌单文件名
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol

from pipeline.aggregate import PlaylistItem

from . import kugou_kgl, kugou_text


class Formatter(Protocol):
    def render(self, items: Iterable[PlaylistItem], fmt: dict[str, Any]) -> str: ...

    def output_filename(self, slug: str, limit: int, fmt: dict[str, Any]) -> str: ...


FORMATTERS: dict[str, Any] = {
    "kugou_kgl": kugou_kgl,
    "kugou_text": kugou_text,
}

SUPPORTED_FORMATS = tuple(FORMATTERS)

# 非歌单文件的输出项（中间结构化数据由 json_dump 单独生成）
SPECIAL_FORMATS = ("json",)


def get_formatter(name: str) -> Any:
    try:
        return FORMATTERS[name]
    except KeyError as exc:
        raise KeyError(f"未知输出格式：{name}（可选 {', '.join(SUPPORTED_FORMATS)}）") from exc
