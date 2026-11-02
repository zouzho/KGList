"""Billboard 榜单适配器（HTML 解析）。

榜单入口：https://www.billboard.com/charts/<chart>/
页面结构变化会导致解析失败，此时按单源失败降级处理，并保留原始快照便于定位。
"""

from __future__ import annotations

import html
import re

from .base import ChartRecord, ChartSpec, HttpClient, SourceError

ROW_MARKER = "o-chart-results-list-row"
TITLE_PATTERN = re.compile(r'id="title-of-a-story"[^>]*>(.*?)</h3>', re.S)
ARTIST_PATTERN = re.compile(r'class="c-label[^"]*"[^>]*>(.*?)</', re.S)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _clean(fragment: str) -> str:
    return html.unescape(TAG_PATTERN.sub("", fragment)).strip()


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    chart = str(spec.params.get("chart") or "hot-100")
    url = f"https://www.billboard.com/charts/{chart}/"
    page = http.get_text(url)

    blocks = page.split(ROW_MARKER)
    if len(blocks) < 2:
        raise SourceError(f"{spec.label}: 页面结构未匹配到榜单行，需检查解析规则")

    records: list[ChartRecord] = []
    for block in blocks[1:]:
        if len(records) >= limit:
            break
        title_match = TITLE_PATTERN.search(block)
        if not title_match:
            continue
        title = _clean(title_match.group(1))
        artist_match = ARTIST_PATTERN.search(block[title_match.end():])
        artist = _clean(artist_match.group(1)) if artist_match else ""
        if not title or not artist:
            continue
        records.append(
            ChartRecord(
                rank=len(records) + 1,
                title=title,
                artists=[artist],
                platform=spec.platform,
                label=spec.label,
                chart=spec.chart,
            )
        )

    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
