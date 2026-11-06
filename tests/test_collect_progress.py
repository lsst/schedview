"""Small real SQLite examples for loading, reruns, and public validation."""

import sqlite3
from contextlib import closing

import pandas as pd
import pytest

from schedview.collect.progress import load_summary_metrics, validate_summary_metrics


@pytest.fixture
def database(tmp_path):
    def create(rows):
        path = tmp_path / "results.db"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.executescript(
                "CREATE TABLE metrics (metric_id INTEGER PRIMARY KEY, run_name VARCHAR, "
                "metric_name VARCHAR, slicer_name VARCHAR, sql_constraint VARCHAR, "
                "metric_info_label VARCHAR);"
                "CREATE TABLE summarystats (stat_id INTEGER PRIMARY KEY, metric_id INTEGER, "
                "summary_name VARCHAR, summary_value FLOAT);"
            )
            for index, overrides in enumerate(rows, start=1):
                row = dict(
                    metric_id=index,
                    stat_id=index,
                    run_name="chimera_20260228",
                    metric_name="Depth",
                    slicer_name="UniSlicer",
                    sql_constraint="",
                    metric_info_label="chimera_g",
                    summary_metric="Mean",
                    summary_value=1.5,
                )
                row.update(overrides)
                connection.execute(
                    "INSERT INTO metrics VALUES (:metric_id, :run_name, :metric_name, :slicer_name, "
                    ":sql_constraint, :metric_info_label)",
                    row,
                )
                connection.execute(
                    "INSERT INTO summarystats VALUES (:stat_id, :metric_id, :summary_metric, :summary_value)",
                    row,
                )
        return path

    return create


@pytest.fixture
def frame(database):
    return load_summary_metrics(database([{}, {"run_name": "chimera_20260301"}]))


def test_load_sources_labels_and_calendar_date(database):
    path = database(
        [
            {"run_name": "chimera_20280229", "summary_value": 2.5},
            {"run_name": "consdb_20280301", "metric_info_label": "consdb_r", "summary_value": 3.5},
            {"run_name": "baseline_20280301", "metric_info_label": "custom region", "summary_value": 4.5},
            {"run_name": "unrelated", "metric_name": None},
        ]
    )
    with pytest.warns(UserWarning, match="excluded 1"):
        result = load_summary_metrics(path)
    by_source = result.set_index("visit_source")
    assert set(by_source.index) == {"chimera", "consdb", "baseline"}
    assert by_source.band.to_dict() == {"chimera": "g", "consdb": "r", "baseline": "all"}
    assert by_source.metric_info_label.to_dict() == {
        "chimera": "chimera_g",
        "consdb": "consdb_r",
        "baseline": "custom region",
    }
    assert by_source.summary_value.to_dict() == {"chimera": 2.5, "consdb": 3.5, "baseline": 4.5}
    assert by_source.loc["chimera", "date"] == pd.Timestamp("2028-02-29")


def test_equal_reruns_keep_highest_stat_provenance(database):
    result = load_summary_metrics(database([{"stat_id": 20}, {"stat_id": 5}]))
    assert len(result) == 1
    assert result.iloc[0].stat_id == 20
    assert result.iloc[0].metric_id == 1
    assert result.iloc[0].summary_value == 1.5


def test_conflicting_reruns(database):
    with pytest.raises(ValueError, match="conflicting summary_value"):
        load_summary_metrics(database([{}, {"summary_value": 2.5}]))


def test_validator_nonmutating_filtered_extra_columns(frame):
    filtered = frame.iloc[[1]].copy()
    filtered.index = ["arbitrary"]
    filtered["extra"] = "untouched"
    original = filtered.copy(deep=True)
    assert validate_summary_metrics(filtered) is None
    pd.testing.assert_frame_equal(filtered, original)


def test_sequence_invariants_across_dates_and_sources(database):
    path = database(
        [
            {"metric_info_label": "region"},
            {"run_name": "consdb_20260301", "metric_info_label": "region", "slicer_name": "HealpixSlicer"},
        ]
    )
    with pytest.raises(ValueError, match="multiple slicer_name"):
        load_summary_metrics(path)


def test_impossible_date_is_contextual(database):
    run = "chimera_20260230"
    with pytest.raises(ValueError, match=run):
        load_summary_metrics(database([{"run_name": run}]))


def test_validator_strict_and_equal_duplicate_modes(frame):
    duplicates = pd.concat([frame, frame.iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate summary record"):
        validate_summary_metrics(duplicates)
    assert validate_summary_metrics(duplicates, allow_duplicates=True) is None


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(ValueError, match="absent.db"):
        load_summary_metrics(path)
    assert not path.exists()
