"""中间结构化数据（JSON）生成器，用于追溯与复核每首歌曲的来源与名次。"""

from __future__ import annotations

import json
from typing import Any, Iterable

from pipeline.aggregate import PlaylistItem


def build_payload(
    *,
    chart: str,
    chart_label: str,
    week: str,
    generated_at: str,
    source_platforms: list[str],
    items: Iterable[PlaylistItem],
    limit: int,
) -> dict[str, Any]:
    return {
        "week": week,
        "chart_type": chart,
        "chart_label": chart_label,
        "limit": limit,
        "generated_at": generated_at,
        "source_platforms": source_platforms,
        "item_count": len(list(items)),
        "items": [
            {
                "rank": item.rank,
                "title": item.title,
                "artists": list(item.artists),
                "score": item.score,
                "appearances": [appearance.as_dict() for appearance in item.appearances],
            }
            for item in items
        ],
    }


def dumps(payload: dict[str, Any], fmt: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=bool(fmt.get("ensure_ascii", False)),
        indent=int(fmt.get("indent", 2)),
    )
