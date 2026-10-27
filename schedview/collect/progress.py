"""Collect validated progress summary records from a MAF ResultsDb.

``SummaryMetrics`` is a pandas DataFrame with ``SUMMARY_COLUMNS``:
integer ``metric_id`` and ``stat_id`` retain database provenance; ``run_name``,
``metric_name``, ``slicer_name``, and ``summary_metric`` are original strings
(the last aliases ``summary_name``). ``sql_constraint`` and
``metric_info_label`` retain original strings or nulls. ``summary_value`` is a
real scalar or missing, including signed infinities. Derived ``visit_source``
is chimera, consdb, or baseline, ``dayobs`` is integer YYYYMMDD, ``band`` is
u/g/r/i/z/y/all, and ``date`` is timezone-naive pandas calendar midnight, not
the physical UTC-12 beginning of the observing night.

Null and empty strings are equivalent only for logical grouping. Original
values are never replaced. One slicer and SQL constraint must describe each
(metric_name, summary_metric, metric_info_label) sequence across dates and
sources. Valid frames have unique (run_name, metric_name, metric_info_label,
summary_metric) records. Extra columns, arbitrary indices, and empty frames
with all required columns are permitted.
"""

import re
import sqlite3
import warnings
from contextlib import closing
from datetime import datetime
from numbers import Integral, Real
from pathlib import Path

import numpy as np
import pandas as pd

from schedview.dayobs import DayObs

SummaryMetrics = pd.DataFrame

SUMMARY_COLUMNS = (
    "metric_id",
    "stat_id",
    "run_name",
    "metric_name",
    "slicer_name",
    "sql_constraint",
    "metric_info_label",
    "summary_metric",
    "summary_value",
    "visit_source",
    "dayobs",
    "band",
    "date",
)

_RUN_PATTERN = re.compile(r"(chimera|consdb|baseline)_([0-9]{8})")
_BANDS = frozenset(("u", "g", "r", "i", "z", "y", "all"))


def _missing(value):
    """Test scalar missingness without accepting arrays as null values."""
    if isinstance(value, (complex, np.complexfloating)):
        return False
    result = pd.isna(value)
    return isinstance(result, (bool, np.bool_)) and bool(result)


def _logical(value):
    return None if _missing(value) or value == "" else value


def _run_fields(run_name):
    match = _RUN_PATTERN.fullmatch(run_name) if isinstance(run_name, str) else None
    if match is None:
        raise ValueError(f"Invalid run_name {run_name!r}: expected <chimera|consdb|baseline>_YYYYMMDD")
    source, date_text = match.groups()
    try:
        date = pd.Timestamp(DayObs.from_date(date_text, int_format="yyyymmdd").date)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid calendar date {date_text!r} in run_name {run_name!r}") from exc
    return source, int(date_text), date


def _band(label, source):
    if isinstance(label, str) and label.startswith(f"{source}_"):
        candidate = label[len(source) + 1 :]
        if candidate in _BANDS:
            return candidate
    return "all"


def _validate_summary_metrics(summary_metrics, *, allow_duplicates=False):
    if not isinstance(summary_metrics, pd.DataFrame):
        raise TypeError("SummaryMetrics must be a pandas DataFrame")
    missing_columns = set(SUMMARY_COLUMNS) - set(summary_metrics.columns)
    if missing_columns:
        raise ValueError(f"SummaryMetrics missing required columns: {', '.join(sorted(missing_columns))}")
    if not summary_metrics.columns.is_unique:
        raise ValueError("SummaryMetrics column names must be unique")

    sequences = {}
    records = {}
    for position, row in enumerate(summary_metrics.loc[:, SUMMARY_COLUMNS].itertuples(index=False)):
        context = f"record {position} (run_name={row.run_name!r}, stat_id={row.stat_id!r})"
        for field in ("metric_id", "stat_id", "dayobs"):
            value = getattr(row, field)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
                raise ValueError(f"{context}: {field} must be an integer")
        for field in ("run_name", "metric_name", "slicer_name", "summary_metric", "visit_source", "band"):
            if not isinstance(getattr(row, field), str):
                raise ValueError(f"{context}: {field} must be a string")
        for field in ("sql_constraint", "metric_info_label"):
            value = getattr(row, field)
            if not isinstance(value, str) and not _missing(value):
                raise ValueError(f"{context}: {field} must be a string or null")
        value = row.summary_value
        if isinstance(value, (bool, np.bool_)) or (not isinstance(value, Real) and not _missing(value)):
            raise ValueError(f"{context}: summary_value must be a real scalar or missing")

        source, dayobs, date = _run_fields(row.run_name)
        for field, expected in (
            ("visit_source", source),
            ("dayobs", dayobs),
            ("band", _band(row.metric_info_label, source)),
        ):
            if getattr(row, field) != expected:
                raise ValueError(f"{context}: {field} must equal {expected!r}")
        if not isinstance(row.date, (datetime, pd.Timestamp, np.datetime64)) or _missing(row.date):
            raise ValueError(f"{context}: date must be a timezone-naive pandas calendar midnight")
        actual_date = pd.Timestamp(row.date)
        if actual_date.tzinfo is not None or actual_date != date:
            raise ValueError(f"{context}: date must be timezone-naive calendar midnight {date}")

        sequence = tuple(
            _logical(getattr(row, field)) for field in ("metric_name", "summary_metric", "metric_info_label")
        )
        invariant = (_logical(row.slicer_name), _logical(row.sql_constraint))
        if sequence in sequences and sequences[sequence] != invariant:
            raise ValueError(
                f"{context}: sequence {sequence!r} has multiple slicer_name or sql_constraint values"
            )
        sequences[sequence] = invariant
        record = (row.run_name, *sequence)
        if record in records:
            previous = records[record]
            equal = (_missing(previous) and _missing(value)) or (
                not _missing(previous) and not _missing(value) and previous == value
            )
            if not equal:
                raise ValueError(
                    f"{context}: conflicting summary_value for {record!r}: {previous!r} vs {value!r}"
                )
            if not allow_duplicates:
                raise ValueError(f"{context}: duplicate summary record {record!r}")
        records[record] = value


def validate_summary_metrics(summary_metrics: SummaryMetrics) -> None:
    """Validate records without mutating, sorting, or deduplicating the frame.

    Raise ``TypeError`` for a non-DataFrame and contextual ``ValueError`` for
    missing columns, invalid value types/derived fields, sequence invariants,
    duplicate records, or conflicting scalar values. Missing measurements and
    non-finite real values are valid gaps; this helper issues no warnings.
    """
    _validate_summary_metrics(summary_metrics)


def load_summary_metrics(db_path: str | Path) -> SummaryMetrics:
    """Read a MAF SQLite database, returning deterministic validated records.

    The database is opened read-only and never created. Only exact supported
    run names are retained, with a warning counting excluded joined summary
    records. Impossible dates and absent schema fail with source context.
    Repeated logical records must have exactly equal finite values, both be
    missing/NaN, or share the same signed infinity. The highest ``stat_id``
    retains its associated provenance. Retained missing/non-finite measurements
    are preserved and counted in a warning, not converted to zero or JSON null.
    """
    path = Path(db_path).expanduser().resolve()
    required = {
        "metrics": (
            "metric_id",
            "run_name",
            "metric_name",
            "slicer_name",
            "sql_constraint",
            "metric_info_label",
        ),
        "summarystats": ("stat_id", "metric_id", "summary_name", "summary_value"),
    }
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
            for table, columns in required.items():
                actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                missing = set(columns) - actual
                if missing:
                    raise ValueError(
                        f"Database {path}: table {table!r} missing required columns: "
                        f"{', '.join(sorted(missing))}"
                    )
            cursor = connection.execute(
                "SELECT m.metric_id, ss.stat_id, m.run_name, m.metric_name, m.slicer_name, "
                "m.sql_constraint, m.metric_info_label, ss.summary_name AS summary_metric, ss.summary_value "
                "FROM metrics m JOIN summarystats ss ON m.metric_id = ss.metric_id "
                "ORDER BY m.run_name, m.metric_name, m.metric_info_label, "
                "ss.summary_name, ss.stat_id, m.metric_id"
            )
            # Avoid inferred string dtypes replacing original SQL NULL labels.
            frame = pd.DataFrame(
                cursor.fetchall(), columns=[item[0] for item in cursor.description], dtype=object
            )
    except (sqlite3.Error, pd.errors.DatabaseError, OSError) as exc:
        raise ValueError(f"Cannot read summary metrics database {path}: {exc}") from exc

    supported = frame.run_name.map(
        lambda name: isinstance(name, str) and _RUN_PATTERN.fullmatch(name) is not None
    )
    excluded = int((~supported).sum())
    if excluded:
        warnings.warn(
            f"Database {path}: excluded {excluded} joined summary records with unsupported run_name",
            UserWarning,
            stacklevel=2,
        )
    frame = frame.loc[supported].copy()
    try:
        fields = [_run_fields(name) for name in frame.run_name]
        frame["visit_source"] = [values[0] for values in fields]
        frame["dayobs"] = pd.Series([values[1] for values in fields], index=frame.index, dtype="int64")
        frame["date"] = pd.Series([values[2] for values in fields], index=frame.index, dtype="datetime64[ms]")
        frame["band"] = [
            _band(label, source) for label, source in zip(frame.metric_info_label, frame.visit_source)
        ]
        frame = frame.loc[:, SUMMARY_COLUMNS]
        _validate_summary_metrics(frame, allow_duplicates=True)
        retained = {}
        for position, row in enumerate(frame.itertuples(index=False)):
            key = tuple(
                _logical(getattr(row, field))
                for field in ("run_name", "metric_name", "metric_info_label", "summary_metric")
            )
            previous = retained.get(key)
            if previous is None or row.stat_id > frame.iloc[previous].stat_id:
                retained[key] = position
        frame = frame.iloc[sorted(retained.values())].reset_index(drop=True)
        validate_summary_metrics(frame)
    except ValueError as exc:
        raise ValueError(f"Database {path}: {exc}") from exc

    missing_count = sum(_missing(value) for value in frame.summary_value)
    nonfinite_count = sum(not _missing(value) and not np.isfinite(value) for value in frame.summary_value)
    if missing_count or nonfinite_count:
        warnings.warn(
            f"Database {path}: retained {missing_count + nonfinite_count} "
            "missing/non-finite summary measurements "
            f"({missing_count} missing, {nonfinite_count} non-finite)",
            UserWarning,
            stacklevel=2,
        )
    return frame
