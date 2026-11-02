"""聚合层：跨源合并去重、加权打分、稳定排序与截断。

去重分两步：
1. 主键去重：以「规范化歌名 + 规范化主歌手」为去重键合并同一来源写法；
2. 歌手署名变体合并：同一规范化歌名下，若不同记录存在歌手交集，
   视为同一首歌（跨平台常出现主歌手/合作歌手署名粒度不同），合并为一条。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from sources.base import ChartRecord

from .normalize import dedupe_key, normalize_artist, normalize_title


@dataclass
class Appearance:
    """一首歌在某个榜单源中的出现记录。"""

    platform: str
    label: str
    rank: int

    def as_dict(self) -> dict[str, Any]:
        return {"platform": self.platform, "label": self.label, "rank": self.rank}


@dataclass
class PlaylistItem:
    """聚合后的歌单条目。"""

    key: str
    title: str
    artists: list[str]
    score: float
    appearances: list[Appearance] = field(default_factory=list)
    first_seen: int = 0
    best_rank: int = 0
    rank: int = 0
    title_key: str = ""
    artist_keys: set[str] = field(default_factory=set)

    @property
    def platforms(self) -> list[str]:
        seen: list[str] = []
        for appearance in self.appearances:
            if appearance.platform not in seen:
                seen.append(appearance.platform)
        return seen

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "title": self.title,
            "artists": list(self.artists),
            "score": self.score,
            "appearances": [appearance.as_dict() for appearance in self.appearances],
        }


def rank_score(rank: int, total: int, mode: str = "linear") -> float:
    """把名次折算为得分：名次越靠前得分越高。"""

    if total <= 0:
        return 0.0
    if mode == "inverse":
        return 1.0 / max(1, rank)
    return max(0.0, (total - rank + 1) / total)


def _sort_items(items: list[PlaylistItem]) -> list[PlaylistItem]:
    """综合分降序；并列时依次按出现平台数、最好名次、首次出现顺序排序，保证结果稳定可复现。"""

    return sorted(
        items,
        key=lambda item: (-item.score, -len(item.platforms), item.best_rank, item.first_seen),
    )


def _merge_artist_variants(items: list[PlaylistItem], rules: dict[str, Any]) -> list[PlaylistItem]:
    """合并同一歌名下歌手署名不同的记录（以歌手集合存在交集为判据）。"""

    if not rules.get("merge_artist_variants", True):
        return items

    groups: dict[str, list[PlaylistItem]] = {}
    for item in items:
        groups.setdefault(item.title_key, []).append(item)

    merged: list[PlaylistItem] = []
    for title_key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        clusters: list[dict[str, Any]] = []
        for item in group:
            target = None
            for cluster in clusters:
                if cluster["artists"] & item.artist_keys:
                    target = cluster
                    break
            if target is None:
                clusters.append({"artists": set(item.artist_keys), "items": [item]})
            else:
                target["artists"] |= item.artist_keys
                target["items"].append(item)

        for cluster in clusters:
            members: list[PlaylistItem] = cluster["items"]
            if len(members) == 1:
                merged.append(members[0])
                continue
            base = min(members, key=lambda item: (item.best_rank, item.first_seen))
            titles: Counter[str] = Counter()
            for member in members:
                titles[member.title] += 1
            merged.append(
                PlaylistItem(
                    key=base.key,
                    title=titles.most_common(1)[0][0],
                    artists=list(base.artists),
                    score=round(sum(member.score for member in members), 6),
                    appearances=[appearance for member in members for appearance in member.appearances],
                    first_seen=min(member.first_seen for member in members),
                    best_rank=min(member.best_rank for member in members),
                    title_key=title_key,
                    artist_keys=set(cluster["artists"]),
                )
            )
    return merged


def aggregate(
    records: Iterable[ChartRecord],
    *,
    limit: int,
    chart_type_weight: float,
    platform_weights: Mapping[str, float],
    rules: dict[str, Any] | None = None,
    mode: str = "linear",
) -> list[PlaylistItem]:
    """把同一类榜单的多来源记录合并去重、加权打分并截断。"""

    rules = rules or {}
    records = list(records)
    totals = Counter((record.platform, record.label) for record in records)

    buckets: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        key = dedupe_key(record.title, record.artists, rules)
        if not key:
            continue
        entry = buckets.get(key)
        if entry is None:
            entry = {
                "score": 0.0,
                "appearances": [],
                "titles": Counter(),
                "artists": list(record.artists),
                "best_rank": record.rank,
                "first_seen": index,
                "artist_keys": set(),
            }
            buckets[key] = entry

        total = totals[(record.platform, record.label)] or limit
        weight = chart_type_weight * float(platform_weights.get(record.platform, 1.0))
        entry["score"] += weight * rank_score(record.rank, total, mode)
        entry["appearances"].append(
            Appearance(platform=record.platform, label=record.label, rank=record.rank)
        )
        entry["titles"][record.title] += 1
        entry["artist_keys"].update(
            normalize_artist(artist, rules) for artist in record.artists if artist.strip()
        )
        if record.rank < entry["best_rank"]:
            entry["best_rank"] = record.rank
            entry["artists"] = list(record.artists)

    items: list[PlaylistItem] = []
    for key, entry in buckets.items():
        title = entry["titles"].most_common(1)[0][0]
        items.append(
            PlaylistItem(
                key=key,
                title=title,
                artists=list(entry["artists"]),
                score=round(entry["score"], 6),
                appearances=entry["appearances"],
                first_seen=entry["first_seen"],
                best_rank=entry["best_rank"],
                title_key=normalize_title(title, rules),
                artist_keys=set(entry["artist_keys"]),
            )
        )

    items = _merge_artist_variants(items, rules)
    selected = _sort_items(items)[:limit]
    for position, item in enumerate(selected, start=1):
        item.rank = position
    return selected
