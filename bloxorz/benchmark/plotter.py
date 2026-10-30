from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path

from bloxorz.benchmark.runner import BenchmarkRecord

METRIC_SPECS: dict[str, tuple[str, str, str]] = {
    "search_time_ms": (
        "Search Time Comparison by Level",
        "Search Time (ms)",
        "time_comparison",
    ),
    "peak_memory_kb": (
        "Peak Memory Comparison by Level",
        "Peak Memory (KB)",
        "memory_comparison",
    ),
    "expanded": (
        "Expanded Nodes Comparison by Level",
        "Expanded Nodes",
        "expanded_comparison",
    ),
    "solution_length": (
        "Solution Length Comparison by Level",
        "Solution Length (moves)",
        "length_comparison",
    ),
}

SOLVER_COLORS: tuple[str, ...] = (
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#d97706",
    "#7c3aed",
    "#0891b2",
)


def _has_matplotlib() -> bool:
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


def _extract_matrix(
    records: Sequence[BenchmarkRecord],
    metric: str,
) -> tuple[list[str], list[str], dict[tuple[str, str], float]]:
    if metric not in METRIC_SPECS:
        raise ValueError(
            f"Unknown metric {metric!r}. Choose from {tuple(METRIC_SPECS)}"
        )

    levels = list(dict.fromkeys(r.level_name for r in records))
    solvers = list(dict.fromkeys(r.solver_name for r in records))
    values: dict[tuple[str, str], float] = {}
    for r in records:
        values[(r.level_name, r.solver_name)] = float(getattr(r, metric))
    return levels, solvers, values


def _render_svg_chart(
    records: Sequence[BenchmarkRecord],
    metric: str,
    title: str,
    ylabel: str,
) -> str:
    levels, solvers, values = _extract_matrix(records, metric)
    width = max(720, 160 + len(levels) * 120)
    height = 440
    margin_left = 80
    margin_right = 40
    margin_top = 60
    margin_bottom = 90
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    max_val = max(values.values(), default=1.0)
    if max_val <= 0:
        max_val = 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2:.1f}" y="30" text-anchor="middle" '
        'font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">'
        f"{html.escape(title)}</text>",
        f'<text x="20" y="{margin_top + plot_h / 2:.1f}" text-anchor="middle" '
        f'transform="rotate(-90 20 {margin_top + plot_h / 2:.1f})" '
        'font-family="sans-serif" font-size="12" fill="#374151">'
        f"{html.escape(ylabel)}</text>",
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" '
        f'y2="{margin_top + plot_h}" stroke="#374151" stroke-width="1.5"/>',
        f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
        f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
        'stroke="#374151" stroke-width="1.5"/>',
    ]

    for i, solver in enumerate(solvers):
        color = SOLVER_COLORS[i % len(SOLVER_COLORS)]
        lx = margin_left + i * 110
        parts.append(f'<rect x="{lx}" y="42" width="12" height="12" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 16}" y="52" font-family="sans-serif" '
            f'font-size="12" fill="#111827">{html.escape(solver)}</text>'
        )

    if levels and solvers:
        group_w = plot_w / len(levels)
        bar_w = min(32.0, (group_w * 0.75) / max(len(solvers), 1))
        for li, level_name in enumerate(levels):
            group_x = (
                margin_left + li * group_w + (group_w - bar_w * len(solvers)) / 2.0
            )
            for si, solver_name in enumerate(solvers):
                val = values.get((level_name, solver_name), 0.0)
                bar_h = (val / max_val) * (plot_h - 20)
                bx = group_x + si * bar_w
                by = margin_top + plot_h - bar_h
                color = SOLVER_COLORS[si % len(SOLVER_COLORS)]
                parts.append(
                    f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bar_w - 2:.2f}" '
                    f'height="{max(bar_h, 0.0):.2f}" fill="{color}"/>'
                )
            label_x = margin_left + (li + 0.5) * group_w
            label_y = margin_top + plot_h + 22
            parts.append(
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="middle" '
                'font-family="sans-serif" font-size="11" fill="#111827">'
                f"{html.escape(level_name)}</text>"
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_matplotlib_chart(
    records: Sequence[BenchmarkRecord],
    metric: str,
    title: str,
    ylabel: str,
    out_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    levels, solvers, values = _extract_matrix(records, metric)
    fig, ax = plt.subplots(figsize=(max(8.0, len(levels) * 1.6), 5.0))

    if levels and solvers:
        n_solvers = len(solvers)
        width = 0.8 / max(n_solvers, 1)
        x_positions = list(range(len(levels)))

        for si, solver_name in enumerate(solvers):
            offset = (si - (n_solvers - 1) / 2.0) * width
            xs = [x + offset for x in x_positions]
            ys = [values.get((lvl, solver_name), 0.0) for lvl in levels]
            color = SOLVER_COLORS[si % len(SOLVER_COLORS)]
            ax.bar(xs, ys, width=width, label=solver_name, color=color)

        ax.set_xticks(x_positions)
        ax.set_xticklabels(levels, rotation=20, ha="right")
        ax.legend()

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_metric(
    records: Sequence[BenchmarkRecord],
    metric: str,
    output_path: str | Path,
) -> Path:
    """Plot a comparison chart for a single metric to `output_path`."""
    if metric not in METRIC_SPECS:
        raise ValueError(
            f"Unknown metric {metric!r}. Choose from {tuple(METRIC_SPECS)}"
        )

    title, ylabel, _ = METRIC_SPECS[metric]
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() != ".svg" and _has_matplotlib():
        _render_matplotlib_chart(records, metric, title, ylabel, out_path)
    else:
        svg_content = _render_svg_chart(records, metric, title, ylabel)
        out_path.write_text(svg_content, encoding="utf-8")

    return out_path


def plot_all_metrics(
    records: Sequence[BenchmarkRecord],
    output_dir: str | Path,
    *,
    fmt: str = "auto",
) -> list[Path]:
    """Generate comparison charts for all 4 benchmark metrics in `output_dir`."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "auto":
        ext = "png" if _has_matplotlib() else "svg"
    else:
        ext = fmt.lstrip(".")

    generated: list[Path] = []
    for metric, (_, _, stem) in METRIC_SPECS.items():
        chart_path = out_dir / f"{stem}.{ext}"
        generated.append(plot_metric(records, metric, chart_path))

    return generated
