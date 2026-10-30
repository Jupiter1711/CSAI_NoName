from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from bloxorz.benchmark.runner import CATEGORY_ORDER, BenchmarkRecord

CSV_FIELDS: tuple[str, ...] = (
    "level_name",
    "category",
    "solver_name",
    "status",
    "found",
    "valid",
    "solution_length",
    "cost",
    "expanded",
    "search_time_ms",
    "peak_memory_kb",
    "path",
)


@dataclass(frozen=True)
class CategorySummary:
    """Aggregated benchmark statistics for a (category, solver_name) pair."""

    category: str
    solver_name: str
    total_levels: int
    solved_levels: int
    valid_levels: int
    avg_expanded: float
    avg_time_ms: float
    avg_memory_kb: float
    avg_length: float
    avg_cost: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def summarize_by_category(
    records: Sequence[BenchmarkRecord],
) -> list[CategorySummary]:
    """Aggregate benchmark metrics grouped by level category and solver."""
    if not records:
        return []

    seen_categories = list(dict.fromkeys(r.category for r in records))
    ordered_categories = [c for c in CATEGORY_ORDER if c in seen_categories] + [
        c for c in seen_categories if c not in CATEGORY_ORDER
    ]
    seen_solvers = list(dict.fromkeys(r.solver_name for r in records))

    summaries: list[CategorySummary] = []
    for category in ordered_categories:
        for solver_name in seen_solvers:
            group = [
                r
                for r in records
                if r.category == category and r.solver_name == solver_name
            ]
            if not group:
                continue

            n = len(group)
            solved = [r for r in group if r.found]
            valid = [r for r in group if r.valid]

            avg_expanded = sum(r.expanded for r in group) / n
            avg_time_ms = sum(r.search_time_ms for r in group) / n
            avg_memory_kb = sum(r.peak_memory_kb for r in group) / n
            avg_length = (
                sum(r.solution_length for r in valid) / len(valid) if valid else 0.0
            )
            avg_cost = sum(r.cost for r in valid) / len(valid) if valid else 0.0

            summaries.append(
                CategorySummary(
                    category=category,
                    solver_name=solver_name,
                    total_levels=n,
                    solved_levels=len(solved),
                    valid_levels=len(valid),
                    avg_expanded=round(avg_expanded, 2),
                    avg_time_ms=round(avg_time_ms, 4),
                    avg_memory_kb=round(avg_memory_kb, 4),
                    avg_length=round(avg_length, 2),
                    avg_cost=round(avg_cost, 2),
                )
            )

    return summaries


def export_csv(records: Sequence[BenchmarkRecord], path: str | Path) -> Path:
    """Export benchmark records to a CSV file."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            row = record.to_dict()
            row["path"] = " ".join(record.path) if record.path is not None else ""
            writer.writerow(row)

    return out_path


def export_json(records: Sequence[BenchmarkRecord], path: str | Path) -> Path:
    """Export benchmark records and category summaries to a JSON file."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "records": [r.to_dict() for r in records],
        "category_summary": [s.to_dict() for s in summarize_by_category(records)],
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return out_path


def format_markdown_table(records: Sequence[BenchmarkRecord]) -> str:
    """Format per-level benchmark results as a GitHub-flavored Markdown table."""
    headers = (
        "| Level | Category | Solver | Status | Valid | Length | Cost | "
        "Expanded | Time (ms) | Peak Mem (KB) |"
    )
    sep = "|---|---|---|---|---|---:|---:|---:|---:|---:|"
    lines = [headers, sep]
    for r in records:
        valid_str = "Yes" if r.valid else "No"
        length_str = str(r.solution_length) if r.found else "-"
        cost_str = f"{r.cost:.1f}" if r.found else "-"
        lines.append(
            f"| {r.level_name} | {r.category} | {r.solver_name} | {r.status} | "
            f"{valid_str} | {length_str} | {cost_str} | {r.expanded} | "
            f"{r.search_time_ms:.4f} | {r.peak_memory_kb:.4f} |"
        )
    return "\n".join(lines)


def format_category_summary_markdown(records: Sequence[BenchmarkRecord]) -> str:
    """Format category-level summary statistics as a Markdown table."""
    summaries = summarize_by_category(records)
    headers = (
        "| Category | Solver | Solved | Valid | Avg Length | Avg Cost | "
        "Avg Expanded | Avg Time (ms) | Avg Peak Mem (KB) |"
    )
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|"
    lines = [headers, sep]
    for s in summaries:
        solved_ratio = f"{s.solved_levels}/{s.total_levels}"
        valid_ratio = f"{s.valid_levels}/{s.total_levels}"
        lines.append(
            f"| {s.category} | {s.solver_name} | {solved_ratio} | {valid_ratio} | "
            f"{s.avg_length:.2f} | {s.avg_cost:.2f} | {s.avg_expanded:.2f} | "
            f"{s.avg_time_ms:.4f} | {s.avg_memory_kb:.4f} |"
        )
    return "\n".join(lines)


def export_markdown(records: Sequence[BenchmarkRecord], path: str | Path) -> Path:
    """Export a complete Markdown report with detailed and summary tables."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    content = "\n\n".join(
        [
            "# Bloxorz Solver Benchmark Report",
            "## 1. Per-Level Results",
            format_markdown_table(records),
            "## 2. Summary by Complexity Category",
            format_category_summary_markdown(records),
        ]
    )
    out_path.write_text(content + "\n", encoding="utf-8")
    return out_path
