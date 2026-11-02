"""采集层公共设施：HTTP 客户端（含重试与礼貌间隔）与数据对象。"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class SourceError(RuntimeError):
    """单个榜单源采集失败。调用方据此降级跳过，不中断整体流程。"""


@dataclass
class ChartRecord:
    """一个榜单条目：一首歌在某一个榜单源中的一条记录。"""

    rank: int
    title: str
    artists: list[str]
    platform: str
    label: str
    chart: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "title": self.title,
            "artists": list(self.artists),
            "platform": self.platform,
            "label": self.label,
            "chart": self.chart,
        }


@dataclass
class ChartSpec:
    """一个榜单源的采集规格，由配置文件生成。"""

    platform: str
    adapter: str
    chart: str
    label: str
    weight: float
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return f"{self.platform}:{self.chart}:{self.label}"


@dataclass
class CollectResult:
    """单个榜单源的采集结果。"""

    spec: ChartSpec
    ok: bool
    records: list[ChartRecord] = field(default_factory=list)
    error: str = ""

    @property
    def source_id(self) -> str:
        return self.spec.source_id


class HttpClient:
    """带指数退避重试与同站点最小请求间隔的轻量 HTTP 客户端（仅依赖标准库）。"""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        retries: int = 2,
        backoff: float = 2.0,
        min_interval: float = 0.6,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.backoff = backoff
        self.min_interval = max(0.0, min_interval)
        self.user_agent = user_agent
        self._last_request_at: dict[str, float] = {}

    def _throttle(self, host: str) -> None:
        last = self._last_request_at.get(host)
        if last is None:
            return
        wait = self.min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, *, referer: str | None = None, accept: str | None = None) -> tuple[bytes, str]:
        attempts = self.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            host = urllib.parse.urlsplit(url).netloc
            self._throttle(host)
            headers = {
                "User-Agent": self.user_agent,
                "Accept": accept or "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            if referer:
                headers["Referer"] = referer
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    self._last_request_at[host] = time.monotonic()
                    return body, charset
            except Exception as exc:  # noqa: BLE001 - 统一收敛为 SourceError
                last_error = exc
                self._last_request_at[host] = time.monotonic()
                LOGGER.warning(
                    "请求失败 %d/%d %s: %s: %s", attempt, attempts, host, type(exc).__name__, exc
                )
                if attempt < attempts:
                    time.sleep(self.backoff * attempt)
        raise SourceError(f"{url} 请求失败：{type(last_error).__name__}: {last_error}") from last_error

    def get_json(self, url: str, *, referer: str | None = None) -> Any:
        body, charset = self.get(url, referer=referer, accept="application/json, text/plain, */*")
        text = body.decode(charset or "utf-8", "replace").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SourceError(f"{url} 响应不是合法 JSON：{exc}") from exc

    def get_text(self, url: str, *, referer: str | None = None) -> str:
        body, charset = self.get(url, referer=referer)
        return body.decode(charset or "utf-8", "replace")


def clean_text(raw: Any) -> str:
    """去除零宽字符与多余空白。"""

    if raw is None:
        return ""
    text = str(raw)
    for token in ("\u200b", "\u200e", "\u200f", "\ufeff"):
        text = text.replace(token, "")
    return " ".join(text.split())


def build_records(items: list[dict[str, Any]], spec: ChartSpec, limit: int, *, title_key="title", artists_key="artists") -> list[ChartRecord]:
    """把适配器解析出的字典列表转换为统一的 ChartRecord 列表。"""

    records: list[ChartRecord] = []
    for index, item in enumerate(items[:limit], start=1):
        title = clean_text(item.get(title_key))
        artists = [clean_text(a) for a in (item.get(artists_key) or []) if clean_text(a)]
        if not title or not artists:
            continue
        records.append(
            ChartRecord(
                rank=index,
                title=title,
                artists=artists,
                platform=spec.platform,
                label=spec.label,
                chart=spec.chart,
            )
        )
    return records
