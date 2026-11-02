"""酷狗音乐榜单适配器。

榜单入口：https://mobiles.kugou.com/api/v3/rank/song?rankid=<rankid>
已核验的 rankid：TOP500 8888 / 新歌榜 74534 / 欧美榜 31310 / 英国单曲榜 4680
"""

from __future__ import annotations

from typing import Any

from .base import ChartRecord, ChartSpec, HttpClient, SourceError, build_records

MULTI_ARTIST_SEPARATORS = ("、", "、", "/", "&")


def _split_artists(text: str) -> list[str]:
    parts = [text]
    for sep in MULTI_ARTIST_SEPARATORS:
        expanded: list[str] = []
        for part in parts:
            expanded.extend(part.split(sep))
        parts = expanded
    return [p.strip() for p in parts if p.strip()]


def _parse_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = (item.get("songname") or "").strip()
    artist_text = (item.get("singername") or "").strip()

    if not title or not artist_text:
        filename = (item.get("filename") or "").strip()
        if " - " in filename:
            head, tail = filename.split(" - ", 1)
            artist_text = artist_text or head.strip()
            title = title or tail.strip()

    if not title or not artist_text:
        return None
    return {"title": title, "artists": _split_artists(artist_text)}


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    rankid = spec.params.get("rankid")
    if not rankid:
        raise SourceError(f"{spec.label}: 缺少 rankid 参数")

    url = (
        "https://mobiles.kugou.com/api/v3/rank/song"
        f"?rankid={rankid}&page=1&pagesize={limit}&plat=0&version=7990"
    )
    payload: dict[str, Any] = http.get_json(url, referer="https://www.kugou.com/")

    info = ((payload.get("data") or {}).get("info")) or []
    items = [parsed for parsed in (_parse_item(item) for item in info) if parsed]

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
