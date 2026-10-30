from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from bloxorz.benchmark.exporters import (
    export_csv,
    export_json,
    export_markdown,
    format_category_summary_markdown,
    format_markdown_table,
)
from bloxorz.benchmark.plotter import plot_all_metrics
from bloxorz.benchmark.runner import (
    get_default_solvers,
    load_levels_from_paths,
    run_benchmarks,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bloxorz.benchmark",
        description="Run Bloxorz AI solver benchmarks and generate reports.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["levels"],
        help="Level JSON files or directories containing level JSON files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="benchmark_results",
        help="Directory to save CSV, JSON, Markdown tables, and plots.",
    )
    parser.add_argument(
        "-s",
        "--solvers",
        nargs="+",
        default=None,
        help="Subset of solver names to run (e.g., BFS DFS UCS A*).",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds per solver run (0 or negative to disable).",
    )
    parser.add_argument(
        "-r",
        "--repeats",
        type=int,
        default=1,
        help="Number of runs per (level, solver) to average time and memory.",
    )
    parser.add_argument(
        "--chart-format",
        choices=("auto", "svg", "png"),
        default="auto",
        help="Output format for comparison charts.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip generating comparison charts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    levels = load_levels_from_paths(args.paths)
    if not levels:
        parser.error(f"No level JSON files found in: {args.paths}")

    available_solvers = get_default_solvers()
    if args.solvers is not None:
        unknown = [name for name in args.solvers if name not in available_solvers]
        if unknown:
            parser.error(
                f"Unknown or unavailable solver(s): {unknown}. "
                f"Available: {list(available_solvers)}"
            )
        solvers = {name: available_solvers[name] for name in args.solvers}
    else:
        solvers = available_solvers

    timeout_s = args.timeout if args.timeout and args.timeout > 0 else None
    records = run_benchmarks(
        levels,
        solvers=solvers,
        timeout_s=timeout_s,
        repeats=args.repeats,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    export_csv(records, out_dir / "benchmark_results.csv")
    export_json(records, out_dir / "benchmark_results.json")
    export_markdown(records, out_dir / "benchmark_report.md")

    if not args.no_plots:
        plot_all_metrics(records, out_dir, fmt=args.chart_format)

    print(format_markdown_table(records))
    print()
    print(format_category_summary_markdown(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
