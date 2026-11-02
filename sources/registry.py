"""适配器注册表：把配置文件中的平台定义转换为榜单采集规格。"""

from __future__ import annotations

from typing import Any, Callable

from . import apple, billboard, deezer, kugou, kuwo, netease, qq
from .base import ChartRecord, ChartSpec, HttpClient

FetchFn = Callable[[ChartSpec, HttpClient, int], list[ChartRecord]]

ADAPTERS: dict[str, FetchFn] = {
    "netease": netease.fetch,
    "qq": qq.fetch,
    "kugou": kugou.fetch,
    "apple": apple.fetch,
    "billboard": billboard.fetch,
    "deezer": deezer.fetch,
    "kuwo": kuwo.fetch,
}


def build_specs(
    config: dict[str, Any],
    *,
    platforms: list[str] | None = None,
    charts: list[str] | None = None,
) -> list[ChartSpec]:
    """按配置生成榜单采集规格，可再按平台名与榜单类型过滤。"""

    specs: list[ChartSpec] = []
    for name, platform in (config.get("platforms") or {}).items():
        if platforms and name not in platforms:
            continue
        if not platform.get("enabled", True):
            continue
        adapter = str(platform.get("adapter") or name)
        if adapter not in ADAPTERS:
            raise KeyError(f"未知适配器：{adapter}（平台 {name}）")
        platform_weight = float(platform.get("weight", 1.0))
        for item in platform.get("charts") or []:
            chart = str(item.get("chart") or "")
            if charts and chart not in charts:
                continue
            specs.append(
                ChartSpec(
                    platform=name,
                    adapter=adapter,
                    chart=chart,
                    label=str(item.get("label") or f"{name}-{chart}"),
                    weight=float(item.get("weight", platform_weight)),
                    params=dict(item.get("params") or {}),
                )
            )
    return specs
