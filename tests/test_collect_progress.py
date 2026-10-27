"""Synthetic SQLite and direct-frame tests for progress collection."""

import os
import sqlite3
import time
import warnings

import numpy as np
import pandas as pd
import pytest

from schedview.collect.progress import (
    SUMMARY_COLUMNS,
    SummaryMetrics,
    load_summary_metrics,
    validate_summary_metrics,
)


@pytest.fixture
def database(tmp_path):
    def create(rows=()):
        path = tmp_path / "results ?#.db"
        with sqlite3.connect(path) as connection:
            connection.executescript(
                "CREATE TABLE metrics (metric_id INTEGER PRIMARY KEY, run_name VARCHAR, "
                "metric_name VARCHAR, slicer_name VARCHAR, sql_constraint VARCHAR, "
                "metric_info_label VARCHAR);"
                "CREATE TABLE summarystats (stat_id INTEGER PRIMARY KEY, metric_id INTEGER, "
                "summary_name VARCHAR, summary_value FLOAT);"
            )
            for index, overrides in enumerate(rows, start=1):
                row = {
                    "metric_id": index,
                    "stat_id": index,
                    "run_name": "chimera_20260228",
                    "metric_name": "Depth",
                    "slicer_name": "UniSlicer",
                    "sql_constraint": "",
                    "metric_info_label": "chimera_g",
                    "summary_metric": "Mean",
                    "summary_value": 1.5,
                }
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


def test_sources_bands_and_original_labels(database):
    rows = [
        {"run_name": f"{source}_20240229", "metric_info_label": f"{source}_{band}"}
        for source in ("chimera", "consdb", "baseline")
        for band in ("u", "g", "r", "i", "z", "y", "all")
    ]
    rows += [
        {"metric_info_label": label}
        for label in (None, "", "consdb_g", "CHIMERA_g", "chimera_G", "chimera_g_extra", "custom|label")
    ]
    # Null and empty labels are logical duplicates, with equal scalar values.
    result = load_summary_metrics(database(rows))
    assert SummaryMetrics is pd.DataFrame
    assert tuple(result.columns) == SUMMARY_COLUMNS
    assert len(result) == len(rows) - 1
    assert set(result.visit_source) == {"chimera", "consdb", "baseline"}
    for row in result.itertuples():
        assert row.band == (
            row.metric_info_label.split("_")[1]
            if row.metric_info_label
            in {f"{row.visit_source}_{band}" for band in ("u", "g", "r", "i", "z", "y", "all")}
            else "all"
        )
        assert row.date == pd.Timestamp(str(row.dayobs))
    assert "custom|label" in result.metric_info_label.values
    assert "" in result.metric_info_label.values


def test_exclusion_counts_joined_rows_and_skips_other_validation(database):
    bad_names = [
        None,
        "CHIMERA_20260228",
        "other_20260228",
        "chimera_2026023",
        "chimera_20260228x",
        "chimera_２０２６０２２８",
        "chimera_20260228\n",
    ]
    path = database(
        [{}] + [{"run_name": name, "metric_name": None, "slicer_name": None} for name in bad_names]
    )
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO summarystats VALUES (100, 2, NULL, 'not numeric')")
    with pytest.warns(UserWarning, match="excluded 8 joined summary records"):
        result = load_summary_metrics(path)
    assert len(result) == 1


def test_all_rows_excluded_returns_valid_empty_schema(database):
    path = database([{"run_name": "unrelated", "metric_name": None, "slicer_name": None}])
    with pytest.warns(UserWarning, match="excluded 1 joined summary records"):
        result = load_summary_metrics(path)
    assert result.empty
    assert tuple(result.columns) == SUMMARY_COLUMNS
    validate_summary_metrics(result)


@pytest.mark.parametrize(
    "run_name", ["chimera_20260230", "consdb_20261301", "baseline_20250229", "chimera_00000000"]
)
def test_impossible_date_is_contextual(database, run_name):
    path = database([{"run_name": run_name}])
    with pytest.raises(ValueError) as error:
        load_summary_metrics(path)
    assert str(path) in str(error.value)
    assert run_name in str(error.value)
    assert run_name.split("_")[1] in str(error.value)


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(ValueError, match="absent.db"):
        load_summary_metrics(path)
    assert not path.exists()


def test_read_only_and_closed_connection(database, monkeypatch):
    path = database([{}])
    connect = sqlite3.connect
    connections = []

    def inspect_connect(database_uri, **kwargs):
        assert kwargs["uri"] is True
        assert database_uri.endswith("?mode=ro")
        connection = connect(database_uri, **kwargs)
        connections.append(connection)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE forbidden (id INTEGER)")
        return connection

    monkeypatch.setattr(sqlite3, "connect", inspect_connect)
    load_summary_metrics(path)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_invalid_sqlite_file(tmp_path):
    path = tmp_path / "invalid.db"
    path.write_bytes(b"not a SQLite database")
    with pytest.raises(ValueError, match="invalid.db.*not a database"):
        load_summary_metrics(path)


@pytest.mark.parametrize(
    "schema",
    ["", "CREATE TABLE metrics (metric_id INTEGER);", "CREATE TABLE summarystats (stat_id INTEGER);"],
)
def test_missing_schema(tmp_path, schema):
    path = tmp_path / "missing-schema.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)
    with pytest.raises(ValueError, match="missing required columns") as error:
        load_summary_metrics(path)
    assert str(path) in str(error.value)
    assert "metrics" in str(error.value)
    assert "run_name" in str(error.value)


def test_missing_summary_column(database):
    path = database()
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE summarystats DROP COLUMN summary_value")
    with pytest.raises(ValueError, match="summarystats.*summary_value"):
        load_summary_metrics(path)


def test_empty_frame(database):
    result = load_summary_metrics(database())
    assert result.empty
    assert tuple(result.columns) == SUMMARY_COLUMNS
    validate_summary_metrics(pd.DataFrame(columns=SUMMARY_COLUMNS))


@pytest.mark.parametrize("values", [(1.5, 1.5), (None, np.nan), (np.inf, np.inf), (-np.inf, -np.inf)])
def test_equal_reruns_keep_highest_stat_provenance(database, values):
    path = database(
        [
            {
                "metric_id": 10,
                "stat_id": 20,
                "summary_value": values[0],
                "metric_info_label": None,
                "sql_constraint": None,
            },
            {
                "metric_id": 30,
                "stat_id": 5,
                "summary_value": values[1],
                "metric_info_label": "",
                "sql_constraint": "",
            },
        ]
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = load_summary_metrics(path)
    assert len(result) == 1
    assert result.iloc[0].stat_id == 20
    assert result.iloc[0].metric_id == 10
    assert result.iloc[0].metric_info_label is None
    assert result.iloc[0].sql_constraint is None
    if values[0] is None or not np.isfinite(values[0]):
        assert len(caught) == 1
        assert "retained 1 missing/non-finite" in str(caught[0].message)
    else:
        assert not caught


@pytest.mark.parametrize(
    "values",
    [
        (1.5, 1.500000000000001),
        (None, 0),
        (None, np.inf),
        (None, -np.inf),
        (np.inf, -np.inf),
        (np.inf, 1),
        (-np.inf, 1),
    ],
)
def test_conflicting_reruns(database, values):
    path = database([{"summary_value": value} for value in values])
    with pytest.raises(ValueError, match="conflicting summary_value"):
        load_summary_metrics(path)


def test_retained_gap_counts(database):
    rows = [
        {"summary_metric": str(i), "summary_value": value}
        for i, value in enumerate([None, np.inf, -np.inf, 0])
    ]
    with pytest.warns(UserWarning, match=r"retained 3 .*\(1 missing, 2 non-finite\)"):
        result = load_summary_metrics(database(rows))
    assert pd.isna(result.summary_value.iloc[0])
    assert result.summary_value.iloc[1] == np.inf
    assert result.summary_value.iloc[2] == -np.inf
    assert result.summary_value.iloc[3] == 0


@pytest.mark.parametrize("field,value", [("slicer_name", "HealpixSlicer"), ("sql_constraint", "band='g'")])
@pytest.mark.parametrize("second_run", ["chimera_20260301", "consdb_20260228"])
def test_sequence_invariants_across_dates_and_sources(database, field, value, second_run):
    path = database(
        [{"metric_info_label": None}, {"run_name": second_run, "metric_info_label": "", field: value}]
    )
    with pytest.raises(ValueError, match="multiple slicer_name or sql_constraint"):
        load_summary_metrics(path)


def test_validator_nonmutating_filtered_extra_columns(frame):
    filtered = frame.iloc[[1]].copy()
    filtered.index = ["arbitrary"]
    filtered["extra"] = "untouched"
    original = filtered.copy(deep=True)
    assert validate_summary_metrics(filtered) is None
    pd.testing.assert_frame_equal(filtered, original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("metric_id", 1.5),
        ("stat_id", True),
        ("dayobs", "20260228"),
        ("metric_name", None),
        ("slicer_name", None),
        ("sql_constraint", 3),
        ("metric_info_label", 5),
        ("summary_metric", None),
        ("summary_value", "1.5"),
        ("summary_value", True),
        ("summary_value", complex(1, 2)),
        ("summary_value", complex(np.nan, 1)),
        ("summary_value", complex(1, np.nan)),
        ("visit_source", "consdb"),
        ("band", "r"),
        ("run_name", "chimera_20260228suffix"),
        ("dayobs", 20260301),
        ("date", pd.Timestamp("2026-02-28T00:00:00Z")),
        ("date", pd.Timestamp("2026-02-28T01:00:00")),
        ("date", "2026-02-28"),
        ("date", pd.NaT),
    ],
)
def test_validator_invalid_fields(frame, field, value):
    invalid = frame.astype({field: object})
    invalid.at[0, field] = value
    with pytest.raises(ValueError, match=field):
        validate_summary_metrics(invalid)


def test_validator_required_columns_and_input(frame):
    with pytest.raises(TypeError, match="DataFrame"):
        validate_summary_metrics([])
    with pytest.raises(ValueError, match="stat_id"):
        validate_summary_metrics(frame.drop(columns="stat_id"))
    with pytest.raises(ValueError, match="column names must be unique"):
        validate_summary_metrics(pd.concat([frame, frame[["date"]]], axis=1))


@pytest.mark.parametrize("value", [None, pd.NA, np.nan, np.inf, -np.inf])
def test_validator_accepts_gaps_without_mutation_or_warning(frame, value):
    frame = frame.astype({"summary_value": object})
    frame.at[0, "summary_value"] = value
    original = frame.copy(deep=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate_summary_metrics(frame)
    assert not caught
    pd.testing.assert_frame_equal(frame, original)


def test_validator_duplicates_conflicts_and_invariants(frame):
    with pytest.raises(ValueError, match="duplicate summary record"):
        validate_summary_metrics(pd.concat([frame, frame.iloc[[0]]]))
    conflict = frame.iloc[[0]].copy()
    conflict["summary_value"] = 2
    with pytest.raises(ValueError, match="conflicting summary_value"):
        validate_summary_metrics(pd.concat([frame, conflict]))
    frame.loc[1, "slicer_name"] = "different"
    with pytest.raises(ValueError, match="multiple slicer_name"):
        validate_summary_metrics(frame)


def test_group_keys_do_not_collide_with_real_text(database):
    result = load_summary_metrics(
        database(
            [
                {"metric_name": "a|b", "summary_metric": "c", "metric_info_label": None},
                {
                    "metric_name": "a",
                    "summary_metric": "b|c",
                    "metric_info_label": "<null>",
                    "slicer_name": "other",
                },
            ]
        )
    )
    assert len(result) == 2


@pytest.mark.parametrize("dayobs", ["20250101", "20280229", "20501231"])
def test_supported_calendar_dates(database, dayobs):
    result = load_summary_metrics(database([{"run_name": f"chimera_{dayobs}"}]))
    assert result.date.iloc[0] == pd.Timestamp(f"{dayobs[:4]}-{dayobs[4:6]}-{dayobs[6:]}")
    validate_summary_metrics(result)
    encoded = result.to_json(orient="records", date_format="epoch", date_unit="ms")
    assert '"date":' in encoded


def test_calendar_dates_timezone_independent(database, monkeypatch):
    path = database(
        [{"run_name": f"chimera_{dayobs}"} for dayobs in (20271231, 20280101, 20280229, 20280301)]
    )
    original_tz = os.environ.get("TZ")
    try:
        frames = []
        for timezone in ("UTC", "Pacific/Honolulu", "Asia/Tokyo"):
            monkeypatch.setenv("TZ", timezone)
            time.tzset()
            frames.append(load_summary_metrics(path))
        for other in frames[1:]:
            pd.testing.assert_frame_equal(frames[0], other)
        assert list(frames[0].date.diff().dropna().dt.days) == [1, 59, 1]
    finally:
        if original_tz is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_tz)
        time.tzset()
