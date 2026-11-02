"""归一化：统一歌名与歌手写法，生成跨源可比较的去重键。"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

# 标点噪声（ASCII 可见标点 + 全角标点 + 常见中文符号），统一转为空格
_PUNCTUATION_RE = re.compile(
    r"[!-/:-@\[-`{-~！-～"
    r"\u00a0\u200b\u3000\u3001\u3002\u3008-\u3011\u3014-\u301f"
    r"\u30fb\u2018\u2019\u201c\u201d\u2013\u2014\u2026]"
)

# 附加信息噪点词，用于剥离版本后缀时兜底处理
_TRAILING_NOISE_RE = re.compile(r"(?i)[\s\-]+(version|edit|mix|demo|live|acoustic)\s*$")


def _apply_patterns(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns or []:
        try:
            text = re.sub(pattern, " ", text)
        except re.error:
            continue
    return text


def _fold(
    text: str,
    *,
    case_insensitive: bool = True,
    strip_punctuation: bool = True,
    collapse_spaces: bool = True,
) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    if strip_punctuation:
        text = _PUNCTUATION_RE.sub(" ", text)
    if collapse_spaces:
        text = " ".join(text.split())
    text = text.strip()
    if case_insensitive:
        text = text.lower()
    return text


def normalize_title(title: str, rules: dict[str, Any] | None = None) -> str:
    """规范化歌名：折叠全半角与大小写、去标点、剥离版本与附加信息。"""

    rules = rules or {}
    text = unicodedata.normalize("NFKC", title or "")
    if rules.get("strip_version_suffix", True):
        text = _apply_patterns(text, rules.get("version_suffix_patterns") or [])
        text = _TRAILING_NOISE_RE.sub(" ", text)
    return _fold(
        text,
        case_insensitive=bool(rules.get("case_insensitive", True)),
        strip_punctuation=bool(rules.get("strip_punctuation", True)),
        collapse_spaces=bool(rules.get("collapse_spaces", True)),
    )


def normalize_artist(artist: str, rules: dict[str, Any] | None = None) -> str:
    """规范化单个歌手名。"""

    rules = rules or {}
    return _fold(
        unicodedata.normalize("NFKC", artist or ""),
        case_insensitive=bool(rules.get("case_insensitive", True)),
        strip_punctuation=bool(rules.get("strip_punctuation", True)),
        collapse_spaces=bool(rules.get("collapse_spaces", True)),
    )


def split_artists(text: str, rules: dict[str, Any] | None = None) -> list[str]:
    """按配置的分隔符拆分多歌手字符串。"""

    rules = rules or {}
    parts = [text or ""]
    for separator in rules.get("artist_split_patterns") or []:
        expanded: list[str] = []
        for part in parts:
            expanded.extend(part.split(separator))
        parts = expanded
    return [part.strip() for part in parts if part.strip()]


def primary_artist(artists: Iterable[str]) -> str:
    """取主歌手（第一个歌手）作为去重键的主字段。"""

    for artist in artists or []:
        if artist and artist.strip():
            return artist.strip()
    return ""


def dedupe_key(title: str, artists: Iterable[str], rules: dict[str, Any] | None = None) -> str:
    """去重键 = 规范化歌名 + 规范化主歌手名。"""

    rules = rules or {}
    artist_list = list(artists or [])
    main = primary_artist(artist_list)
    if not main:
        return ""
    return f"{normalize_title(title, rules)}|{normalize_artist(main, rules)}"
