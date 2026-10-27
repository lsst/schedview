"""Synthetic reporting, input grammar, and installed command checks."""

import json
import sqlite3
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from bokeh.models import Div
from click.testing import CliRunner

from schedview.app import progress_explore as app


@pytest.fixture
def summary_database(tmp_path):
    """Minimal ResultsDb with finite/missing scalars and calendar labels."""
    path = tmp_path / "results.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE metrics (metric_id INTEGER, run_name TEXT, metric_name TEXT, "
            "slicer_name TEXT, sql_constraint TEXT, metric_info_label TEXT);"
            "CREATE TABLE summarystats (stat_id INTEGER, metric_id INTEGER, "
            "summary_name TEXT, summary_value REAL);"
        )
        for index, (run, value) in enumerate(
            [
                ("chimera_20240229", 1.234567890123456),
                ("consdb_20240301", None),
                ("baseline_20240302", float("inf")),
                ("baseline_20240303", float("-inf")),
            ],
            start=1,
        ):
            connection.execute(
                "INSERT INTO metrics VALUES (?, ?, 'Metric', 'Slicer', NULL, NULL)", (index, run)
            )
            connection.execute("INSERT INTO summarystats VALUES (?, ?, 'Mean', ?)", (index, index, value))
    return path


def test_data_records_dates_nulls_precision_and_copy(summary_database, tmp_path, monkeypatch):
    records = app.load_summary_metrics(str(summary_database))
    records["extra_text"] = "literal NaN Infinity -Infinity"
    original = records.copy(deep=True)
    validations = []
    validator = app.validate_summary_metrics

    def validate(frame):
        validations.append(frame)
        validator(frame)

    monkeypatch.setattr(app, "load_summary_metrics", lambda path: records)
    monkeypatch.setattr(app, "validate_summary_metrics", validate)
    path = tmp_path / "data.json"
    result = CliRunner().invoke(app.make_summary_progress_data, [str(summary_database), str(path)])
    assert result.exit_code == 0, result.output
    assert len(validations) == 1
    assert validations[0] is records
    pd.testing.assert_frame_equal(records, original)

    def reject_nonstandard_constant(value):
        pytest.fail(f"Nonstandard JSON scalar: {value}")

    output = json.loads(path.read_text(), parse_constant=reject_nonstandard_constant)
    assert isinstance(output, list)
    assert len(output) == 4
    by_run = {row["run_name"]: row for row in output}
    finite = by_run["chimera_20240229"]
    assert finite["summary_value"] == pytest.approx(1.234567890123456, rel=1e-15)
    assert finite["date"] == 1709164800000
    assert finite["dayobs"] == 20240229
    assert isinstance(finite["metric_id"], int)
    assert isinstance(finite["stat_id"], int)
    assert finite["metric_info_label"] is None
    assert finite["sql_constraint"] is None
    assert finite["extra_text"] == "literal NaN Infinity -Infinity"
    assert all(by_run[run]["summary_value"] is None for run in by_run if run != "chimera_20240229")
    assert np.isposinf(records.loc[records.run_name == "baseline_20240302", "summary_value"].iloc[0])
    assert np.isneginf(records.loc[records.run_name == "baseline_20240303", "summary_value"].iloc[0])


def test_data_validation_failure_writes_nothing(summary_database, tmp_path, monkeypatch):
    records = app.load_summary_metrics(str(summary_database)).drop(columns="run_name")
    monkeypatch.setattr(app, "load_summary_metrics", lambda path: records)
    output = tmp_path / "invalid.json"
    result = CliRunner().invoke(app.make_summary_progress_data, [str(summary_database), str(output)])
    assert result.exit_code != 0
    assert "run_name" in result.output
    assert "Cannot export" in result.stderr
    assert not output.exists()


def test_empty_export_and_finite_precision(summary_database, tmp_path):
    with sqlite3.connect(summary_database) as connection:
        connection.execute("UPDATE metrics SET run_name = 'unrelated'")
    output = tmp_path / "empty.json"
    with pytest.warns(UserWarning, match="excluded 4 joined summary records"):
        result = CliRunner().invoke(app.make_summary_progress_data, [str(summary_database), str(output)])
    assert result.exit_code == 0, result.output
    assert output.read_text() == "[]"

    values = [1e-20, -1.234567890123456e20, 1.79e308, -1.79e308]
    with sqlite3.connect(summary_database) as connection:
        for index, value in enumerate(values, start=1):
            connection.execute(
                "UPDATE metrics SET run_name = ? WHERE metric_id = ?", (f"chimera_2026010{index}", index)
            )
            connection.execute("UPDATE summarystats SET summary_value = ? WHERE stat_id = ?", (value, index))
    result = CliRunner().invoke(app.make_summary_progress_data, [str(summary_database), str(output)])
    assert result.exit_code == 0, result.output
    actual = [row["summary_value"] for row in json.loads(output.read_text())]
    assert actual == pytest.approx(values, rel=1e-14, abs=0)


@pytest.mark.parametrize(
    "source,kind,external",
    [
        ("https://example.invalid/data", "auto", True),
        ("HTTP://example.invalid/results.db", "auto", True),
        ("./progress.json", "auto", True),
        ("../data/progress.json?rev=2#fragment", "auto", True),
        ("/served/progress.json", "auto", True),
        ("progress.JSON", "auto", True),
        ("results.db", "auto", False),
        ("results.sqlite?name=.json", "auto", False),
        ("results.json", "database", False),
        ("./endpoint", "json-url", True),
        ("https://example.invalid/results.db", "database", False),
    ],
)
def test_plot_input_grammar(source, kind, external, tmp_path, monkeypatch):
    loaded = []
    plotted = []
    frame = pd.DataFrame()

    def load(path):
        loaded.append(path)
        return frame

    def plot(records):
        plotted.append(records)
        return Div(text="synthetic plot")

    monkeypatch.setattr(app, "load_summary_metrics", load)
    monkeypatch.setattr(app, "make_summary_progress_plot", plot)
    output = tmp_path / "page.html"
    result = CliRunner().invoke(
        app.make_summary_progress_plot_cli,
        [source, str(output), "--input-kind", kind, "--title", "Test title"],
    )
    assert result.exit_code == 0, result.output
    assert loaded == ([] if external else [source])
    assert len(plotted) == 1
    if external:
        assert plotted[0] == source
    else:
        assert plotted[0] is frame
    html = output.read_text()
    assert "<title>Test title</title>" in html
    assert "synthetic plot" in html
    assert sorted(path.name for path in tmp_path.iterdir()) == ["page.html"]


def test_database_html_embeds_data_without_json(summary_database, tmp_path):
    output = tmp_path / "embedded.html"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [str(summary_database), str(output)])
    assert result.exit_code == 0, result.output
    html = output.read_text()
    assert "chimera_20240229" in html
    assert "baseline_20240303" in html
    assert "cdn.bokeh.org" in html
    assert not list(tmp_path.glob("*.json"))


def test_external_html_never_loads_local_json(tmp_path, monkeypatch):
    source = "./not-present.json?rev=3"

    def unexpected_load(path):
        pytest.fail(f"External input was read at generation time: {path}")

    monkeypatch.setattr(app, "load_summary_metrics", unexpected_load)
    output = tmp_path / "external.html"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [source, str(output)])
    assert result.exit_code == 0, result.output
    assert source in output.read_text()
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("command", [app.make_summary_progress_data, app.make_summary_progress_plot_cli])
@pytest.mark.parametrize("args", [[], ["only-one-argument"]])
def test_two_positionals_required(command, args):
    result = CliRunner().invoke(command, args)
    assert result.exit_code == 2
    assert "Usage:" in result.output


@pytest.mark.parametrize("command", [app.make_summary_progress_data, app.make_summary_progress_plot_cli])
def test_database_and_output_failures(command, summary_database, tmp_path):
    missing = tmp_path / "missing.db"
    output = tmp_path / "output"
    result = CliRunner().invoke(command, [str(missing), str(output)])
    assert result.exit_code != 0
    assert "missing.db" in result.stderr
    assert not missing.exists()
    assert not output.exists()

    invalid = tmp_path / "invalid.db"
    with sqlite3.connect(invalid):
        pass
    result = CliRunner().invoke(command, [str(invalid), str(output)])
    assert result.exit_code != 0
    assert "invalid.db" in result.stderr
    assert not output.exists()

    unreachable = tmp_path / "missing-directory" / "output"
    result = CliRunner().invoke(command, [str(summary_database), str(unreachable)])
    assert result.exit_code != 0
    assert "missing-directory" in result.stderr


def test_unknown_input_kind(tmp_path):
    result = CliRunner().invoke(
        app.make_summary_progress_plot_cli, ["data", str(tmp_path / "page.html"), "--input-kind", "guess"]
    )
    assert result.exit_code == 2
    assert "Invalid value" in result.output


@pytest.mark.parametrize("command", [app.make_summary_progress_data, app.make_summary_progress_plot_cli])
@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_cannot_overwrite_database(command, alias, summary_database, tmp_path):
    original = summary_database.read_bytes()
    output = summary_database
    if alias != "same":
        output = tmp_path / "output.db"
        if alias == "symlink":
            output.symlink_to(summary_database)
        else:
            output.hardlink_to(summary_database)
    result = CliRunner().invoke(command, [str(summary_database), str(output)])
    assert result.exit_code != 0
    assert "refusing to overwrite" in result.stderr
    assert summary_database.read_bytes() == original


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
@pytest.mark.parametrize("suffix", ["", "?rev=2#latest"])
def test_output_cannot_overwrite_external_json(alias, suffix, tmp_path):
    source = tmp_path / "progress.json"
    source.write_text("[]")
    output = source
    if alias != "same":
        output = tmp_path / "page.html"
        if alias == "symlink":
            output.symlink_to(source)
        else:
            output.hardlink_to(source)
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, ["./progress.json" + suffix, str(output)])
    assert result.exit_code != 0
    assert "refusing to overwrite" in result.stderr
    assert source.read_text() == "[]"


def test_external_json_is_resolved_beside_page_and_not_read(tmp_path, monkeypatch):
    source = tmp_path / "progress data.json"
    source.write_text("not JSON: generation must not read this")
    monkeypatch.setattr(app, "load_summary_metrics", lambda path: pytest.fail("External input read"))
    output = tmp_path / "page.html"
    url = "./progress%20data.json?rev=2#latest"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [url, str(output)])
    assert result.exit_code == 0, result.output
    assert url in output.read_text()
    assert source.read_text() == "not JSON: generation must not read this"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [url, str(source)])
    assert result.exit_code != 0
    assert "refusing to overwrite" in result.stderr
    assert source.read_text() == "not JSON: generation must not read this"


def test_packaging_registration():
    project = tomllib.loads(Path(__file__).parents[1].joinpath("pyproject.toml").read_text())
    scripts = project["project"]["scripts"]
    assert (
        scripts["make_summary_progress_data"] == "schedview.app.progress_explore:make_summary_progress_data"
    )
    assert (
        scripts["make_summary_progress_plot"]
        == "schedview.app.progress_explore:make_summary_progress_plot_cli"
    )
    assert "click" in project["project"]["dependencies"]


@pytest.mark.parametrize("name", ["make_summary_progress_data", "make_summary_progress_plot"])
def test_installed_entrypoint_help(name):
    entries = {entry.name: entry for entry in metadata.distribution("schedview").entry_points}
    assert name in entries, "Reinstall the editable package to refresh installed entrypoints"
    command = Path(sys.executable).parent / name
    assert command.exists()
    result = subprocess.run([str(command), "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert f"Usage: {name}" in result.stdout


def test_installed_commands_generate_reports(summary_database, tmp_path):
    """Exercise installed commands, not just Click objects or metadata."""
    bin_dir = Path(sys.executable).parent
    data_path = tmp_path / "installed.json"
    page_path = tmp_path / "installed.html"
    for name, source, destination in [
        ("make_summary_progress_data", summary_database, data_path),
        ("make_summary_progress_plot", summary_database, page_path),
    ]:
        result = subprocess.run(
            [str(bin_dir / name), str(source), str(destination)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert destination.exists()
    assert isinstance(json.loads(data_path.read_text()), list)
    assert "chimera_20240229" in page_path.read_text()
    assert not (tmp_path / "installed_data.json").exists()
