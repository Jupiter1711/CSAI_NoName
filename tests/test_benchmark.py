import csv
import json
import time
from pathlib import Path

import pytest

from bloxorz.benchmark import (
    BenchmarkTimeoutError,
    classify_level,
    export_csv,
    export_json,
    export_markdown,
    format_category_summary_markdown,
    format_markdown_table,
    get_default_solvers,
    load_levels_from_paths,
    measure_solver,
    plot_all_metrics,
    plot_metric,
    run_benchmarks,
    summarize_by_category,
    verify_solution,
)
from bloxorz.benchmark.cli import main as cli_main
from bloxorz.core import BloxorzProblem, parse_level
from bloxorz.solvers import astar
from bloxorz.solvers.base import SearchResult


@pytest.fixture()
def simple_level():
    return parse_level(
        {
            "name": "Level 1 - Simple",
            "grid": [
                "#####",
                "#S##G",
                "#####",
            ],
        }
    )


@pytest.fixture()
def fragile_level():
    return parse_level(
        {
            "name": "Level 2 - Fragile",
            "grid": [
                "#####",
                "#SF#G",
                "#####",
            ],
        }
    )


@pytest.fixture()
def switches_level():
    return parse_level(
        {
            "name": "Level 3 - Switches",
            "grid": [
                "####..#####",
                "#S##BB###G#",
                "#O##..#####",
            ],
            "open_bridges": [[1, 4], [1, 5]],
            "switches": [
                {"pos": [2, 1], "mode": "toggle", "bridges": [[1, 4], [1, 5]]},
            ],
        }
    )


@pytest.fixture()
def combined_level():
    return parse_level(
        {
            "name": "Level 4 - Combined",
            "grid": [
                "#####",
                "#SP#G",
                "#####",
            ],
            "switches": [
                {"pos": [1, 2], "targets": [[0, 1], [2, 1]]},
            ],
        }
    )


def test_classify_level(simple_level, fragile_level, switches_level, combined_level):
    assert classify_level(simple_level) == "simple"
    assert classify_level(fragile_level) == "fragile"
    assert classify_level(switches_level) == "switches"
    assert classify_level(combined_level) == "combined"

    fragile_and_bridge = parse_level(
        {
            "name": "Fragile + Bridge",
            "grid": ["#SFBG"],
            "open_bridges": [[0, 3]],
        }
    )
    assert classify_level(fragile_and_bridge) == "combined"


def test_verify_solution_and_astar_contract(simple_level):
    problem = BloxorzProblem(simple_level)
    result = astar.solve(problem)

    assert result.found
    assert verify_solution(problem, result.path)
    assert not verify_solution(problem, None)
    assert not verify_solution(problem, ["U", "U", "U"])
    assert not verify_solution(problem, ["R"])


def test_get_default_solvers_includes_astar(simple_level):
    solvers = get_default_solvers()
    assert "A*" in solvers
    problem = BloxorzProblem(simple_level)
    res = solvers["A*"](problem)
    assert res.found


def test_measure_solver_statuses(simple_level):
    rec_ok = measure_solver(simple_level, "A*", astar.solve, repeats=2)
    assert rec_ok.status == "OK"
    assert rec_ok.found is True
    assert rec_ok.valid is True
    assert rec_ok.solution_length > 0
    assert rec_ok.expanded > 0
    assert rec_ok.search_time_ms >= 0.0
    assert rec_ok.peak_memory_kb >= 0.0
    assert rec_ok.search_time_s == pytest.approx(rec_ok.search_time_ms / 1000.0)

    def unsolved_solver(problem: BloxorzProblem) -> SearchResult:
        return SearchResult(None, expanded=5, cost=0.0)

    rec_unsolved = measure_solver(simple_level, "DummyUnsolved", unsolved_solver)
    assert rec_unsolved.status == "UNSOLVED"
    assert not rec_unsolved.found
    assert not rec_unsolved.valid

    def invalid_solver(problem: BloxorzProblem) -> SearchResult:
        return SearchResult(["R"], expanded=2, cost=1.0)

    rec_invalid = measure_solver(simple_level, "DummyInvalid", invalid_solver)
    assert rec_invalid.status == "INVALID"
    assert rec_invalid.found
    assert not rec_invalid.valid

    def buggy_solver(problem: BloxorzProblem) -> SearchResult:
        raise RuntimeError("solver crashed")

    rec_err = measure_solver(simple_level, "DummyBuggy", buggy_solver)
    assert rec_err.status == "ERROR: RuntimeError"
    assert not rec_err.found

    def slow_solver(problem: BloxorzProblem) -> SearchResult:
        time.sleep(0.15)
        return SearchResult(None, 0, 0.0)

    rec_timeout = measure_solver(simple_level, "DummySlow", slow_solver, timeout_s=0.03)
    assert rec_timeout.status == "TIMEOUT"
    assert not rec_timeout.found

    with pytest.raises(ValueError, match="repeats"):
        measure_solver(simple_level, "A*", astar.solve, repeats=0)


def test_exporters_and_plotter(
    tmp_path: Path, simple_level, fragile_level, switches_level
):
    levels = [simple_level, fragile_level, switches_level]
    records = run_benchmarks(levels, solvers={"A*": astar.solve})
    assert len(records) == 3

    summaries = summarize_by_category(records)
    assert [s.category for s in summaries] == ["simple", "fragile", "switches"]
    assert all(s.valid_levels == 1 for s in summaries)

    csv_path = export_csv(records, tmp_path / "results.csv")
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert rows[0]["solver_name"] == "A*"

    json_path = export_json(records, tmp_path / "results.json")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 3
    assert len(payload["category_summary"]) == 3

    md_path = export_markdown(records, tmp_path / "report.md")
    md_text = md_path.read_text(encoding="utf-8")
    assert "Level 1 - Simple" in md_text
    assert "Summary by Complexity Category" in md_text
    assert "A*" in format_markdown_table(records)
    assert "simple" in format_category_summary_markdown(records)

    charts = plot_all_metrics(records, tmp_path / "charts", fmt="svg")
    assert len(charts) == 4
    for chart in charts:
        assert chart.exists()
        assert "<svg" in chart.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown metric"):
        plot_metric(records, "invalid_metric", tmp_path / "bad.svg")


def test_cli_end_to_end(tmp_path: Path):
    levels_dir = tmp_path / "levels"
    levels_dir.mkdir()
    level_file = levels_dir / "level01_simple.json"
    level_file.write_text(
        json.dumps(
            {
                "name": "CLI Simple Level",
                "grid": [
                    "#####",
                    "#S##G",
                    "#####",
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_levels_from_paths([levels_dir, level_file])
    assert len(loaded) == 2

    out_dir = tmp_path / "out"
    exit_code = cli_main(
        [
            str(levels_dir),
            "-o",
            str(out_dir),
            "-s",
            "A*",
            "--chart-format",
            "svg",
        ]
    )
    assert exit_code == 0
    assert (out_dir / "benchmark_results.csv").exists()
    assert (out_dir / "benchmark_results.json").exists()
    assert (out_dir / "benchmark_report.md").exists()
    assert (out_dir / "time_comparison.svg").exists()
    assert (out_dir / "memory_comparison.svg").exists()
    assert (out_dir / "expanded_comparison.svg").exists()
    assert (out_dir / "length_comparison.svg").exists()
    assert issubclass(BenchmarkTimeoutError, TimeoutError)
