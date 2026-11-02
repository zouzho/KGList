"""统一命令行入口。

用法示例：
    python main.py run
    python main.py run --chart hot --chart new
    python main.py run --platform netease --platform qq
    python main.py run --week 2026-11-02 --limit 50 -v
"""

from __future__ import annotations

import argparse
import sys

from runner import CHART_TYPES, run, setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chart-playlist-aggregator",
        description="全球音乐榜单聚合歌单生成器：采集各大音乐平台欧洲榜/热歌榜/新歌榜，去重聚合后输出酷狗歌单",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="执行一次完整流程")
    run_parser.add_argument("--config", default="config/settings.yaml", help="主配置文件路径")
    run_parser.add_argument("--format-config", default="config/format.yaml", help="输出格式配置文件路径")
    run_parser.add_argument("--week", default=None, help="周次/输出目录名，默认取执行日（UTC，YYYY-MM-DD）")
    run_parser.add_argument(
        "--chart", action="append", dest="charts", choices=list(CHART_TYPES),
        help="只处理指定榜单类型（europe/hot/new），可重复",
    )
    run_parser.add_argument("--platform", action="append", dest="platforms", help="只处理指定平台，可重复")
    run_parser.add_argument("--limit", type=int, default=None, help="每个歌单保留条数，默认取配置文件")
    run_parser.add_argument("--workers", type=int, default=6, help="采集并发数")
    run_parser.add_argument("--output-dir", default=None, help="输出根目录，默认取配置文件")
    run_parser.add_argument("--allow-partial", action="store_true", help="允许某类榜单无数据时仍继续产出")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(bool(getattr(args, "verbose", False)))
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
