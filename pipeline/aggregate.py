"""聚合层：跨源合并去重、加权打分、稳定排序与截断。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from sources.base import ChartRecord

from .normalize import dedupe_key


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
            }
            buckets[key] = entry

        total = totals[(record.platform, record.label)] or limit
        weight = chart_type_weight * float(platform_weights.get(record.platform, 1.0))
        entry["score"] += weight * rank_score(record.rank, total, mode)
        entry["appearances"].append(
            Appearance(platform=record.platform, label=record.label, rank=record.rank)
        )
        entry["titles"][record.title] += 1
        if record.rank < entry["best_rank"]:
            entry["best_rank"] = record.rank
            entry["artists"] = list(record.artists)

    items: list[PlaylistItem] = []
    for key, entry in buckets.items():
        title = entry["titles"].most_common(1)[0][0]
        appearances: list[Appearance] = entry["appearances"]
        items.append(
            PlaylistItem(
                key=key,
                title=title,
                artists=list(entry["artists"]),
                score=round(entry["score"], 6),
                appearances=appearances,
                first_seen=entry["first_seen"],
                best_rank=entry["best_rank"],
            )
        )

    # 综合分降序；并列时依次按出现平台数、最好名次、首次出现顺序排序，保证结果稳定可复现
    items.sort(
        key=lambda item: (
            -item.score,
            -len(item.platforms),
            item.best_rank,
            item.first_seen,
        )
    )

    selected = items[:limit]
    for position, item in enumerate(selected, start=1):
        item.rank = position
    return selected
