"""Real reporting commands and direct input-overwrite protection."""

import json
import sqlite3
from contextlib import closing

import pytest
from click.testing import CliRunner

from schedview.app import progress_explore as app


@pytest.fixture
def summary_database(tmp_path):
    path = tmp_path / "results.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(
            "CREATE TABLE metrics (metric_id INTEGER, run_name TEXT, metric_name TEXT, "
            "slicer_name TEXT, sql_constraint TEXT, metric_info_label TEXT);"
            "CREATE TABLE summarystats (stat_id INTEGER, metric_id INTEGER, "
            "summary_name TEXT, summary_value REAL);"
        )
        for index, (run, value) in enumerate(
            [("chimera_20280229", 1.25), ("consdb_20280301", None)], start=1
        ):
            connection.execute(
                "INSERT INTO metrics VALUES (?, ?, 'Report metric', 'Slicer', NULL, NULL)", (index, run)
            )
            connection.execute("INSERT INTO summarystats VALUES (?, ?, 'Mean', ?)", (index, index, value))
    return path


def test_data_records_include_value_calendar_epoch_and_null_gap(summary_database, tmp_path):
    output = tmp_path / "data.json"
    result = CliRunner().invoke(app.make_summary_progress_data, [str(summary_database), str(output)])
    assert result.exit_code == 0, result.output
    rows = json.loads(output.read_text())
    assert len(rows) == 2
    assert rows[0]["run_name"] == "chimera_20280229"
    assert rows[0]["summary_value"] == 1.25
    assert rows[0]["date"] == 1835395200000
    assert rows[1]["summary_value"] is None


def test_database_html_embeds_data_without_json(summary_database, tmp_path):
    output = tmp_path / "embedded.html"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [str(summary_database), str(output)])
    assert result.exit_code == 0, result.output
    assert "chimera_20280229" in output.read_text()
    assert "Report metric" in output.read_text()
    assert not list(tmp_path.glob("*.json"))


def test_external_html_never_loads_local_json(tmp_path):
    source = "./not-present.json"
    output = tmp_path / "external.html"
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, [source, str(output)])
    assert result.exit_code == 0, result.output
    assert source in output.read_text()
    assert not (tmp_path / "not-present.json").exists()


def test_explicit_database_kind_reads_json_named_database(summary_database, tmp_path):
    source = summary_database.rename(tmp_path / "results.json")
    output = tmp_path / "page.html"
    result = CliRunner().invoke(
        app.make_summary_progress_plot_cli, [str(source), str(output), "--input-kind", "database"]
    )
    assert result.exit_code == 0, result.output
    assert "chimera_20280229" in output.read_text()


def test_explicit_json_url_kind_keeps_suffixless_endpoint_external(tmp_path):
    output = tmp_path / "page.html"
    result = CliRunner().invoke(
        app.make_summary_progress_plot_cli, ["./endpoint", str(output), "--input-kind", "json-url"]
    )
    assert result.exit_code == 0, result.output
    assert "./endpoint" in output.read_text()


@pytest.mark.parametrize("command", [app.make_summary_progress_data, app.make_summary_progress_plot_cli])
def test_output_cannot_overwrite_database(command, summary_database):
    original = summary_database.read_bytes()
    result = CliRunner().invoke(command, [str(summary_database), str(summary_database)])
    assert result.exit_code != 0
    assert "overwrite" in result.stderr
    assert summary_database.read_bytes() == original


def test_output_cannot_overwrite_external_json(tmp_path):
    source = tmp_path / "progress.json"
    source.write_text("[]")
    original = source.read_bytes()
    result = CliRunner().invoke(app.make_summary_progress_plot_cli, ["./progress.json", str(source)])
    assert result.exit_code != 0
    assert "overwrite" in result.stderr
    assert source.read_bytes() == original
