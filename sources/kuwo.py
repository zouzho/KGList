"""酷我音乐榜单适配器（默认关闭）。

酷我公开接口要求 csrf 令牌（取自站点 cookie），本模块已按该流程实现。
当前网络环境下该接口返回 "The request is illegal!"，因此在配置中默认关闭，
完成接入验证后在 config/settings.yaml 中把 kuwo.enabled 改为 true 即可启用。
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.request
from typing import Any

from .base import DEFAULT_USER_AGENT, ChartRecord, ChartSpec, HttpClient, SourceError, build_records

HOME_URL = "https://www.kuwo.cn/"
BANG_URL = "https://www.kuwo.cn/api/www/bang/bang/musicList"


def _split_artists(text: str) -> list[str]:
    parts = text.replace("&", "&").split("&")
    return [part.strip() for part in parts if part.strip()]


def fetch(spec: ChartSpec, http: HttpClient, limit: int) -> list[ChartRecord]:
    bang_id = spec.params.get("bang_id")
    if not bang_id:
        raise SourceError(f"{spec.label}: 缺少 bang_id 参数")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Referer": HOME_URL}

    with opener.open(urllib.request.Request(HOME_URL, headers=headers), timeout=http.timeout) as resp:
        resp.read(4096)

    token = next((cookie.value for cookie in jar if cookie.name in {"kw_token", "token"}), "")
    if not token:
        raise SourceError(f"{spec.label}: 未能获取 csrf 令牌")

    api = f"{BANG_URL}?bangId={bang_id}&pn=1&rn={limit}&httpsStatus=1"
    api_headers = dict(headers)
    api_headers["csrf"] = token
    api_headers["Cookie"] = "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar)

    with opener.open(urllib.request.Request(api, headers=api_headers), timeout=http.timeout) as resp:
        payload: dict[str, Any] = json.loads(resp.read().decode("utf-8", "replace"))

    if not payload.get("success", False):
        raise SourceError(f"{spec.label}: 接口返回 {payload.get('message') or payload}")

    music_list = (payload.get("data") or {}).get("musicList") or []
    items = [{"title": entry.get("name"), "artists": _split_artists(entry.get("artist") or "")} for entry in music_list]

    records = build_records(items, spec, limit)
    if not records:
        raise SourceError(f"{spec.label}: 未解析到任何条目")
    return records
