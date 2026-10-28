import json

import pytest

from chunk_dedup_lab.bench import (
    Scenario,
    compare_methods,
    edit_reuse,
    insertion_curve,
    run_scenario,
    size_curve,
)
from chunk_dedup_lab.cli import main
from chunk_dedup_lab.report import (
    render_chunks,
    render_compare,
    render_dedup,
    render_edit_reuse,
    render_insertion_curve,
    render_json,
    render_scenario,
    render_size_curve,
)

SMALL = 32 * 1024


def test_scenario_reports_both_methods():
    payload = run_scenario(Scenario(name="small", base_size=SMALL))
    assert payload["fixed"]["chunk_count"] > 0
    assert payload["cdc"]["chunk_count"] > 0
    assert 0 <= payload["cdc"]["ratio"] <= 1


def test_scenario_accepts_custom_parameters():
    payload = run_scenario(Scenario(name="custom", base_size=SMALL, fixed_size=8192, bits=10))
    assert payload["fixed"]["avg_chunk"] > 4096
    assert payload["cdc"]["avg_chunk"] < payload["fixed"]["avg_chunk"]


def test_compare_methods_returns_four_chunkers():
    results = compare_methods(SMALL)
    labels = [result.label for result in results]
    assert labels[0].startswith("fixed")
    assert sum(1 for label in labels if label.startswith("cdc")) == 3


def test_cdc_beats_fixed_on_ratio():
    results = compare_methods(SMALL)
    fixed = next(result for result in results if result.label.startswith("fixed"))
    cdc = next(result for result in results if result.label == "cdc 2^12")
    assert cdc.ratio < fixed.ratio


def test_insertion_curve_shows_the_fixed_penalty():
    rows = insertion_curve(SMALL, bits=12)
    first = rows[0]
    assert first["insert"] == 1
    assert first["fixed_reuse"] < 0.05
    assert first["cdc_reuse"] > 0.7


def test_edit_reuse_covers_every_edit():
    rows = edit_reuse(SMALL, bits=12)
    assert len(rows) == 5
    assert all(0 <= row["cdc_reuse"] <= 1 for row in rows)


def test_size_curve_is_monotone_in_target():
    rows = size_curve(SMALL)
    targets = [row["target"] for row in rows]
    assert targets == sorted(targets)
    assert all(row["fixed_count"] >= 1 for row in rows)


def test_reports_render():
    payload = run_scenario(Scenario(name="small", base_size=SMALL))
    results = compare_methods(SMALL)
    assert "Scenario: small" in render_scenario(payload)
    assert "method" in render_compare(results)
    assert "ratio" in render_dedup(results[0])
    assert "insert" in render_insertion_curve(insertion_curve(SMALL))
    assert "edit" in render_edit_reuse(edit_reuse(SMALL))
    assert "target" in render_size_curve(size_curve(SMALL))
    assert "digest" in render_chunks(results and [])
    assert json.loads(render_json(payload))["scenario"] == "small"


@pytest.mark.parametrize(
    "argv",
    [
        ["bench", "--size-kib", "32"],
        ["bench", "--size-kib", "32", "--format", "json"],
        ["compare", "--size-kib", "32"],
        ["compare", "--size-kib", "32", "--format", "json"],
        ["insertions", "--size-kib", "32"],
        ["edits", "--size-kib", "32"],
        ["sizes", "--size-kib", "32"],
        ["chunks", "--size-kib", "32", "--mode", "fixed", "--limit", "3"],
        ["chunks", "--size-kib", "32", "--mode", "cdc", "--limit", "3"],
    ],
)
def test_cli_commands_succeed(argv, capsys):
    assert main(argv) == 0
    assert capsys.readouterr().out


def test_cli_rejects_bad_bits(capsys):
    assert main(["bench", "--size-kib", "32", "--bits", "0"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_chunks_reports_average(capsys):
    assert main(["chunks", "--size-kib", "32", "--limit", "2"]) == 0
    assert "bytes average" in capsys.readouterr().out
