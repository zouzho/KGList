"""Apple Music（Apple Marketing Tools RSS）榜单适配器。

榜单入口：https://rss.applemarketingtools.com/api/v2/{country}/music/most-played/{limit}/songs.json
以国家维度提供各地区热歌榜，用于欧洲榜（gb/de/fr/es）与热歌榜（us）。
"""

from __future__ import annotations

from typing import Any

from .base import ChartRecord, ChartSpec, HttpClient, SourceError, build_records


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    country = str(spec.params.get("country") or "us").lower()
    feed = str(spec.params.get("feed") or "most-played")

    url = (
        "https://rss.applemarketingtools.com/api/v2/"
        f"{country}/music/{feed}/{limit}/songs.json"
    )
    payload: dict[str, Any] = http.get_json(url)

    results = ((payload.get("feed") or {}).get("results")) or []
    items = [{"title": entry.get("name"), "artists": [entry.get("artistName")]} for entry in results]

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
