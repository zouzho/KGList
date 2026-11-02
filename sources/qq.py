"""QQ 音乐榜单适配器。

榜单入口：https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg?topid=<topid>&format=json
已核验的 topid：巅峰榜·热歌 26 / 巅峰榜·新歌 27
"""

from __future__ import annotations

from typing import Any

from .base import ChartRecord, ChartSpec, HttpClient, SourceError, build_records


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    topid = spec.params.get("topid")
    if not topid:
        raise SourceError(f"{spec.label}: 缺少 topid 参数")

    url = (
        "https://c.y.qq.com/v8/fcg-bin/fcg_v8_toplist_cp.fcg"
        f"?topid={topid}&format=json&platform=yqq&needNewCode=0&num={limit}"
    )
    payload: dict[str, Any] = http.get_json(url, referer="https://y.qq.com/")

    songs = payload.get("songlist") or []
    items = []
    for song in songs:
        data = song.get("data") or {}
        singers = data.get("singer") or []
        items.append(
            {
                "title": data.get("songname") or data.get("songorig"),
                "artists": [s.get("name") for s in singers if isinstance(s, dict)],
            }
        )

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
