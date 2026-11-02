"""编排层：采集 -> 归一化去重 -> 聚合排序 -> 生成 -> 校验 -> 留存。

一次运行产出三类歌单（欧洲榜、热歌榜、新歌榜），每类最多 100 首：
- output/<周次>/<slug>_top100.txt  酷狗音乐歌单文件
- output/<周次>/<slug>.json        中间结构化数据（可还原来源与名次）
- output/<周次>/raw/*.json         各榜单源原始快照
- logs/run-<周次>.md               运行摘要
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from formatters import json_dump, registry
from pipeline.aggregate import PlaylistItem, aggregate
from sources.base import ChartSpec, CollectResult, HttpClient
from sources.registry import ADAPTERS, build_specs
from validators import checks

LOGGER = logging.getLogger("aggregator")

CHART_TYPES = ("europe", "hot", "new")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-")
    return cleaned.lower() or "source"


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_text_file(path: Path, text: str, fmt: dict[str, Any]) -> None:
    encoding = str(fmt.get("encoding") or "utf-8")
    errors = str(fmt.get("encoding_errors") or "strict")
    data = text.encode(encoding, errors)
    if fmt.get("bom"):
        data = b"\xef\xbb\xbf" + data
    _write_bytes(path, data)


def collect_all(specs: list[ChartSpec], http: HttpClient, limit: int, workers: int) -> list[CollectResult]:
    """并发采集各榜单源；单源失败只记录异常并降级，不中断整体流程。"""

    def task(spec: ChartSpec) -> CollectResult:
        try:
            records = ADAPTERS[spec.adapter](spec, http, limit)
            LOGGER.info("采集成功 %-58s 条数=%d", spec.source_id, len(records))
            return CollectResult(spec=spec, ok=True, records=records)
        except Exception as exc:  # noqa: BLE001 - 单源失败降级
            LOGGER.warning("采集失败 %-58s %s: %s", spec.source_id, type(exc).__name__, exc)
            return CollectResult(spec=spec, ok=False, error=f"{type(exc).__name__}: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(task, specs))


def run(args: Any) -> int:
    settings = load_yaml(args.config)
    format_config = load_yaml(args.format_config)
    json_fmt = format_config.get("json_record") or {}

    charts_meta = settings.get("charts") or {}
    chart_order = [chart for chart in (charts_meta.get("order") or list(CHART_TYPES)) if chart in CHART_TYPES]
    chart_labels = charts_meta.get("labels") or {}
    chart_slugs = charts_meta.get("slugs") or {}
    require_all = bool(charts_meta.get("require_all", True)) and not args.allow_partial

    limits = settings.get("limits") or {}
    limit = int(args.limit or limits.get("per_chart", 100))
    per_source_limit = int(limits.get("max_items_per_source", limit))

    scoring = settings.get("scoring") or {}
    chart_type_weights = scoring.get("chart_type_weights") or {}
    rank_score_mode = str(scoring.get("rank_score_mode") or "linear")
    dedupe_rules = settings.get("dedupe") or {}

    http_config = settings.get("http") or {}
    http = HttpClient(
        timeout=float(http_config.get("timeout_seconds", 20)),
        retries=int(http_config.get("retries", 2)),
        backoff=float(http_config.get("backoff_seconds", 2.0)),
        min_interval=float(http_config.get("min_interval_seconds", 0.6)),
        user_agent=str(http_config.get("user_agent") or ""),
    )

    platform_weights = {
        name: float(platform.get("weight", 1.0))
        for name, platform in (settings.get("platforms") or {}).items()
    }

    output_config = settings.get("output") or {}
    output_formats = [str(name) for name in (output_config.get("formats") or ["kugou_kgl", "kugou_text"])]
    known_formats = set(registry.SUPPORTED_FORMATS) | set(registry.SPECIAL_FORMATS)
    unknown_formats = [name for name in output_formats if name not in known_formats]
    if unknown_formats:
        LOGGER.error(
            "存在不支持的输出格式：%s（可选 %s）",
            ", ".join(unknown_formats),
            ", ".join(sorted(known_formats)),
        )
        return 2

    week = str(args.week or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    output_root = Path(args.output_dir or output_config.get("dir") or "output")
    week_dir = output_root / week
    report_dir = Path(output_config.get("report_dir") or "logs")
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    requested_charts = [chart for chart in chart_order if not args.charts or chart in args.charts]
    if not requested_charts:
        LOGGER.error("没有可处理的榜单类型，请检查 --chart 参数")
        return 2

    specs = build_specs(settings, platforms=args.platforms, charts=requested_charts)
    if not specs:
        LOGGER.error("按当前配置没有启用任何榜单源，请检查 config/settings.yaml")
        return 2

    LOGGER.info("周次=%s 榜单类型=%s 榜单源=%d 个", week, ",".join(requested_charts), len(specs))

    results = collect_all(specs, http, per_source_limit, max(1, int(args.workers)))

    # 留存原始快照
    raw_dir = week_dir / str(output_config.get("snapshot_subdir") or "raw")
    if output_config.get("write_snapshot", True):
        for result in results:
            snapshot = {
                "week": week,
                "collected_at": generated_at,
                "spec": {
                    "platform": result.spec.platform,
                    "chart": result.spec.chart,
                    "label": result.spec.label,
                    "weight": result.spec.weight,
                    "params": result.spec.params,
                },
                "ok": result.ok,
                "error": result.error,
                "records": [record.as_dict() for record in result.records],
            }
            name = f"{_slug(result.spec.platform)}-{result.spec.chart}-{_slug(result.spec.label)}.json"
            _write_bytes(
                raw_dir / name,
                json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
            )

    by_chart: dict[str, list[CollectResult]] = {chart: [] for chart in requested_charts}
    for result in results:
        if result.spec.chart in by_chart:
            by_chart[result.spec.chart].append(result)

    playlist_summary: list[dict[str, Any]] = []
    problems: list[str] = []
    missing_charts: list[str] = []

    for chart in requested_charts:
        chart_results = by_chart[chart]
        ok_results = [result for result in chart_results if result.ok]
        records = [record for result in ok_results for record in result.records]
        label = str(chart_labels.get(chart) or chart)

        if not records:
            missing_charts.append(chart)
            message = f"{label}：没有可用的榜单数据（{len(chart_results)} 个来源全部失败或无数据）"
            LOGGER.error(message)
            problems.append(message)
            playlist_summary.append(
                {
                    "chart": chart,
                    "label": label,
                    "count": 0,
                    "sources_ok": len(ok_results),
                    "sources_total": len(chart_results),
                    "files": [],
                    "problems": [message],
                }
            )
            continue

        items: list[PlaylistItem] = aggregate(
            records,
            limit=limit,
            chart_type_weight=float(chart_type_weights.get(chart, 1.0)),
            platform_weights=platform_weights,
            rules=dedupe_rules,
            mode=rank_score_mode,
        )

        slug = str(chart_slugs.get(chart) or chart)

        chart_problems: list[str] = []
        playlist_files: list[str] = []
        for format_name in output_formats:
            if format_name not in registry.SUPPORTED_FORMATS:
                continue
            fmt = dict(format_config.get(format_name) or {})
            fmt["_label"] = label
            fmt["_limit"] = limit
            fmt["_week"] = week
            formatter = registry.get_formatter(format_name)
            playlist_text = formatter.render(items, fmt)
            playlist_path = week_dir / formatter.output_filename(slug, limit, fmt)
            _write_text_file(playlist_path, playlist_text, fmt)
            playlist_files.append(str(playlist_path))
            if format_name == "kugou_kgl":
                chart_problems += checks.validate_kugou_kgl(
                    items=items, text=playlist_text, fmt=fmt, limit=limit, chart_label=label
                )
            else:
                chart_problems += checks.validate_playlist(
                    items=items, text=playlist_text, fmt=fmt, limit=limit, chart_label=label
                )

        payload = json_dump.build_payload(
            chart=chart,
            chart_label=label,
            week=week,
            generated_at=generated_at,
            source_platforms=sorted({result.spec.platform for result in ok_results}),
            items=items,
            limit=limit,
        )
        payload_text = json_dump.dumps(payload, json_fmt)
        payload_path = week_dir / f"{slug}.json"
        _write_bytes(payload_path, payload_text.encode("utf-8"))
        chart_problems += checks.validate_payload(
            payload_text, limit=limit, item_count=len(items), chart_label=label
        )
        problems.extend(chart_problems)

        sources_ok = len(ok_results)
        sources_total = len(chart_results)
        LOGGER.info(
            "歌单完成 %-6s 条数=%3d 来源=%d/%d 输出=%s",
            label, len(items), sources_ok, sources_total,
            "、".join(Path(path).name for path in playlist_files),
        )
        playlist_summary.append(
            {
                "chart": chart,
                "label": label,
                "count": len(items),
                "sources_ok": sources_ok,
                "sources_total": sources_total,
                "files": playlist_files + [str(payload_path)],
                "problems": chart_problems,
            }
        )

    if require_all and missing_charts:
        LOGGER.error("以下歌单未产出，任务判定失败：%s", ", ".join(missing_charts))

    report_dir.mkdir(parents=True, exist_ok=True)
    _write_bytes(
        report_dir / f"collect-{week}.jsonl",
        "\n".join(
            json.dumps(
                {
                    "platform": result.spec.platform,
                    "chart": result.spec.chart,
                    "label": result.spec.label,
                    "ok": result.ok,
                    "count": len(result.records),
                    "error": result.error,
                },
                ensure_ascii=False,
            )
            for result in results
        ).encode("utf-8")
        + b"\n",
    )
    report_text = _render_report(
        week=week,
        generated_at=generated_at,
        results=results,
        summary=playlist_summary,
        problems=problems,
        limit=limit,
    )
    _write_bytes(report_dir / f"run-{week}.md", report_text.encode("utf-8"))
    LOGGER.info("运行报告：%s", report_dir / f"run-{week}.md")

    success = not problems and (not require_all or not missing_charts)
    LOGGER.info(
        "运行结束：%s（歌单 %d/%d，数据源成功 %d/%d，问题 %d 条）",
        "成功" if success else "失败",
        len([entry for entry in playlist_summary if entry["count"]]),
        len(requested_charts),
        len([result for result in results if result.ok]),
        len(results),
        len(problems),
    )
    for problem in problems:
        LOGGER.error("问题：%s", problem)
    return 0 if success else 1


def _render_report(
    *,
    week: str,
    generated_at: str,
    results: list[CollectResult],
    summary: list[dict[str, Any]],
    problems: list[str],
    limit: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# 榜单歌单运行报告 · {week}")
    lines.append("")
    lines.append(f"- 生成时间（UTC）：{generated_at}")
    lines.append(f"- 每类歌单条数上限：{limit}")
    lines.append(f"- 榜单源：成功 {len([r for r in results if r.ok])} / 共 {len(results)}")
    lines.append("")
    lines.append("## 歌单产出")
    lines.append("")
    lines.append("| 歌单 | 条数 | 成功来源 | 输出文件 |")
    lines.append("| --- | --- | --- | --- |")
    for entry in summary:
        files = "、".join(f"`{Path(path).name}`" for path in entry["files"]) or "—"
        lines.append(
            f"| {entry['label']} | {entry['count']} | {entry['sources_ok']}/{entry['sources_total']} | {files} |"
        )
    lines.append("")
    lines.append("## 采集明细")
    lines.append("")
    lines.append("| 平台 | 榜单类型 | 榜单名称 | 状态 | 条数 | 说明 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for result in results:
        status = "成功" if result.ok else "失败（已降级）"
        detail = result.error.replace("|", "/") if result.error else "—"
        lines.append(
            f"| {result.spec.platform} | {result.spec.chart} | {result.spec.label} | {status} | "
            f"{len(result.records)} | {detail} |"
        )
    lines.append("")
    lines.append("## 校验结果")
    lines.append("")
    if problems:
        lines.extend(f"- {problem}" for problem in problems)
    else:
        lines.append("- 条数、去重、行格式与中间数据一致性校验全部通过")
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 酷狗歌单文件（.kgl）格式参数见 `config/format.yaml`，首次使用请在酷狗音乐客户端列表空白处右键「导入列表」实际导入验证。")
    lines.append("- 单源失败不影响整体产出，失败来源已在上方采集明细中标注。")
    return "\n".join(lines) + "\n"
