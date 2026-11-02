"""网易云音乐榜单适配器。

榜单入口：https://music.163.com/api/playlist/detail?id=<playlist_id>
已核验的榜单 ID：热歌榜 3778678 / 新歌榜 3779629 / 欧美热歌榜 2809513713
"""

from __future__ import annotations

from typing import Any

from .base import ChartRecord, ChartSpec, HttpClient, SourceError, build_records


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    playlist_id = spec.params.get("playlist_id")
    if not playlist_id:
        raise SourceError(f"{spec.label}: 缺少 playlist_id 参数")

    url = f"https://music.163.com/api/playlist/detail?id={playlist_id}"
    payload: dict[str, Any] = http.get_json(url, referer="https://music.163.com/")

    if payload.get("code") != 200:
        raise SourceError(f"{spec.label}: 接口返回 code={payload.get('code')}")

    tracks = ((payload.get("result") or {}).get("tracks")) or []
    items = []
    for track in tracks:
        artists = track.get("artists") or track.get("ar") or []
        items.append(
            {
                "title": track.get("name"),
                "artists": [a.get("name") for a in artists if isinstance(a, dict)],
            }
        )

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
