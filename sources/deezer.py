"""Deezer 榜单适配器（公开 JSON 接口，无授权要求）。

榜单入口：https://api.deezer.com/chart/{genre_id}/tracks
说明：该接口在部分网络区域不可达，单源失败按降级处理。
"""

from __future__ import annotations

from typing import Any

from .base import ChartRecord, ChartSpec, HttpClient, SourceError, build_records


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    genre_id = spec.params.get("genre_id", 0)
    url = f"https://api.deezer.com/chart/{genre_id}/tracks?limit={limit}"
    payload: dict[str, Any] = http.get_json(url)

    if payload.get("error"):
        raise SourceError(f"{spec.label}: 接口返回错误 {payload.get('error')}")

    items = []
    for entry in payload.get("data") or []:
        artist = (entry.get("artist") or {}).get("name")
        items.append({"title": entry.get("title") or entry.get("title_short"), "artists": [artist]})

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
