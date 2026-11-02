"""采集层：各平台榜单适配器。

每个适配器模块暴露统一的 ``fetch(spec, http, limit) -> list[ChartRecord]`` 接口，
适配器之间相互隔离，平台接口变更只需修改对应模块。
"""

from .base import ChartRecord, ChartSpec, CollectResult, HttpClient, SourceError

__all__ = ["ChartRecord", "ChartSpec", "CollectResult", "HttpClient", "SourceError"]
