"""歌单文件与中间数据的校验规则。

校验不通过时由调用方把任务判定为失败，不产出不完整歌单。
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from pipeline.aggregate import PlaylistItem


def validate_playlist(
    *,
    items: Iterable[PlaylistItem],
    text: str,
    fmt: dict[str, Any],
    limit: int,
    chart_label: str,
) -> list[str]:
    """校验歌单文件内容：条数、去重、行格式与完整性。"""

    items = list(items)
    problems: list[str] = []
    line_ending = str(fmt.get("line_ending") or "\n")
    separator = str(fmt.get("separator") or " - ")
    fields = list(fmt.get("field_order") or ["title", "artist"])

    if not items:
        problems.append(f"{chart_label}: 歌单为空")
    if len(items) > limit:
        problems.append(f"{chart_label}: 条数 {len(items)} 超过上限 {limit}")

    keys = [item.key for item in items]
    if len(keys) != len(set(keys)):
        problems.append(f"{chart_label}: 存在重复条目（去重键重复）")

    ranks = [item.rank for item in items]
    if ranks != list(range(1, len(items) + 1)):
        problems.append(f"{chart_label}: 序号不连续（应为 1..{len(items)}）")

    for item in items:
        if not item.title or not item.artists or not separator.join(
            value for value in [item.title, str(fmt.get("artist_separator") or "/").join(item.artists)] if value
        ):
            problems.append(f"{chart_label}: 存在字段缺失的条目：{item.title!r}")

    if line_ending:
        body = text[:-len(line_ending)] if text.endswith(line_ending) else text
        lines = body.split(line_ending)
    else:
        lines = text.splitlines()

    header = str(fmt.get("header") or "")
    footer = str(fmt.get("footer") or "")
    if header and lines and lines[0] == header:
        lines = lines[1:]
    if footer and lines and lines[-1] == footer:
        lines = lines[:-1]

    if len(lines) != len(items):
        problems.append(f"{chart_label}: 文件行数 {len(lines)} 与条目数 {len(items)} 不一致")
    if any(not line.strip() for line in lines):
        problems.append(f"{chart_label}: 文件中存在空行")
    if len(set(lines)) != len(lines):
        problems.append(f"{chart_label}: 文件中存在重复行")
    if len(fields) > 1 and any(separator not in line for line in lines):
        problems.append(f"{chart_label}: 存在缺少字段分隔符的行")

    prefix_template = str(fmt.get("line_prefix") or "")
    if not prefix_template and any(
        line.split(".", 1)[0].strip().isdigit() for line in lines if "." in line
    ):
        problems.append(f"{chart_label}: 未配置序号前缀，但文件行首出现序号")

    return problems


def validate_payload(payload_text: str, *, limit: int, item_count: int, chart_label: str) -> list[str]:
    """校验中间 JSON 数据的可解析性与一致性。"""

    problems: list[str] = []
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        return [f"{chart_label}: 中间数据不是合法 JSON：{exc}"]

    if payload.get("item_count") != item_count:
        problems.append(f"{chart_label}: 中间数据 item_count 与歌单条目数不一致")
    if len(payload.get("items") or []) != item_count:
        problems.append(f"{chart_label}: 中间数据 items 数量与歌单条目数不一致")
    if item_count > limit:
        problems.append(f"{chart_label}: 中间数据条数超过上限 {limit}")
    if any(not item.get("appearances") for item in payload.get("items") or []):
        problems.append(f"{chart_label}: 存在缺少来源信息的条目，无法追溯")
    return problems
