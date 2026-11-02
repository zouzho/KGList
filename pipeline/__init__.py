"""处理层：归一化、去重键、聚合排序与截断。"""

from .aggregate import Appearance, PlaylistItem, aggregate, rank_score
from .normalize import dedupe_key, normalize_artist, normalize_title, split_artists

__all__ = [
    "Appearance",
    "PlaylistItem",
    "aggregate",
    "rank_score",
    "dedupe_key",
    "normalize_artist",
    "normalize_title",
    "split_artists",
]
