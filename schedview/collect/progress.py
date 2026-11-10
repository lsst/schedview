"""Collect validated progress summary records from a MAF ResultsDb.

``SummaryMetrics`` is a pandas DataFrame with ``SUMMARY_COLUMNS``:
integer ``metric_id`` and ``stat_id`` retain database provenance; ``run_name``,
``metric_name``, ``slicer_name``, and ``summary_metric`` are original strings
(the last aliases ``summary_name``). ``sql_constraint`` and
``metric_info_label`` retain original strings or nulls. ``summary_value`` is a
real scalar or missing, including signed infinities. Derived ``visit_source``
is chimera, consdb, or the configured reference tag (baseline by default),
``dayobs`` is integer YYYYMMDD, ``band`` is
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
from typing import TypeAlias

import numpy as np
import pandas as pd

from schedview.dayobs import DayObs

SummaryMetrics: TypeAlias = pd.DataFrame
"""Records contract above, not a distinct runtime DataFrame subclass."""

SUMMARY_COLUMNS: tuple[str, ...] = (
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

_VALID_BANDS: frozenset[str] = frozenset(("u", "g", "r", "i", "z", "y", "all"))

_SEQUENCE_FIELDS: tuple[str, ...] = ("metric_name", "summary_metric", "metric_info_label")
"""Fields identifying one plotted sequence across dates and sources."""
_RECORD_FIELDS: tuple[str, ...] = ("run_name", "metric_name", "metric_info_label", "summary_metric")
"""Fields identifying one logical record; duplicates share these values."""

_REQUIRED_DB_COLUMNS: dict[str, tuple[str, ...]] = {
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
"""Columns the MAF results database must provide, by table."""


def _is_missing_scalar(value: object) -> bool:
    """Test whether a scalar is None/NaN/NaT; arrays are never missing."""
    if isinstance(value, (complex, np.complexfloating)):
        return False
    result = pd.isna(value)
    return isinstance(result, (bool, np.bool_)) and bool(result)


def _grouping_key_value(value: object) -> object:
    """Map null and empty strings to None so they group together.

    Used only to build comparison keys; the original label or constraint
    is never rewritten.
    """
    return None if _is_missing_scalar(value) or value == "" else value


def _validate_reference_sim_tag(reference_sim_tag: str) -> None:
    """Require one literal reference prefix, not consdb or chimera."""
    if (
        not isinstance(reference_sim_tag, str)
        or not reference_sim_tag
        or reference_sim_tag in ("consdb", "chimera")
    ):
        raise ValueError(
            f"Invalid reference_sim_tag {reference_sim_tag!r}: "
            "must be a nonempty string other than 'consdb' or 'chimera'"
        )


def _parse_run_name(run_name: object, pattern: re.Pattern[str]) -> tuple[str, int, pd.Timestamp]:
    """Split a run name into (source, YYYYMMDD integer, calendar midnight).

    Raise ``ValueError`` for an unsupported name or impossible date.
    """
    match = pattern.fullmatch(run_name) if isinstance(run_name, str) else None
    if match is None:
        raise ValueError(f"Invalid run_name {run_name!r}: expected full match of {pattern.pattern!r}")
    source, date_text = match.groups()
    try:
        # The date label is not the physical UTC-12 start of the night.
        date = pd.Timestamp(DayObs.from_date(date_text, int_format="yyyymmdd").date)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid calendar date {date_text!r} in run_name {run_name!r}") from exc
    return source, int(date_text), date


def _band_from_label(label: object, source: str) -> str:
    """Return the band named by a ``<source>_<band>`` label, else ``"all"``.

    Only a label whose prefix matches the run's source exactly, with a known
    band suffix, names a band; absent or unrecognized labels mean all bands.
    """
    if isinstance(label, str) and label.startswith(f"{source}_"):
        candidate = label[len(source) + 1 :]
        if candidate in _VALID_BANDS:
            return candidate
    return "all"


def validate_summary_metrics(
    summary_metrics: SummaryMetrics, *, reference_sim_tag: str = "baseline", allow_duplicates: bool = False
) -> None:
    """Validate records without mutating, sorting, or deduplicating the frame.

    Raise ``TypeError`` for a non-DataFrame and contextual ``ValueError`` for
    missing columns, invalid value types/derived fields, sequence invariants,
    duplicate records, or conflicting scalar values. Missing measurements and
    non-finite real values are valid gaps; this function issues no warnings.
    Set ``allow_duplicates=True`` to permit equal reruns before collection
    deduplication. Conflicting scalar values are rejected in either mode.

    ``reference_sim_tag`` is a literal, case-sensitive source prefix, default
    ``"baseline"``. An alternate replaces baseline; pass the same tag used for
    collection, plotting, and export. Empty/non-string and reserved
    consdb/chimera tags raise ``ValueError``, including for empty frames.
    """
    _validate_reference_sim_tag(reference_sim_tag)
    pattern = re.compile(rf"(chimera|consdb|{re.escape(reference_sim_tag)})_([0-9]{{8}})")
    # Check structure first so row access cannot obscure a missing column.
    if not isinstance(summary_metrics, pd.DataFrame):
        raise TypeError("SummaryMetrics must be a pandas DataFrame")
    missing_columns = set(SUMMARY_COLUMNS) - set(summary_metrics.columns)
    if missing_columns:
        raise ValueError(f"SummaryMetrics missing required columns: {', '.join(sorted(missing_columns))}")
    if not summary_metrics.columns.is_unique:
        raise ValueError("SummaryMetrics column names must be unique")

    slicer_and_constraint_by_sequence: dict[tuple[object, ...], tuple[object, object]] = {}
    """Logical sequence -> slicer/constraint, independent of run/source."""
    value_by_record: dict[tuple[object, ...], object] = {}
    """Logical run/sequence -> original scalar, including gaps/infinities."""

    for position, row in enumerate(summary_metrics.loc[:, SUMMARY_COLUMNS].itertuples(index=False)):
        context = f"record {position} (run_name={row.run_name!r}, stat_id={row.stat_id!r})"

        # Reject malformed scalars before deriving fields or comparing keys.
        for field in ("metric_id", "stat_id", "dayobs"):
            value = getattr(row, field)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
                raise ValueError(f"{context}: {field} must be an integer")
        for field in ("run_name", "metric_name", "slicer_name", "summary_metric", "visit_source", "band"):
            if not isinstance(getattr(row, field), str):
                raise ValueError(f"{context}: {field} must be a string")
        for field in ("sql_constraint", "metric_info_label"):
            value = getattr(row, field)
            if not isinstance(value, str) and not _is_missing_scalar(value):
                raise ValueError(f"{context}: {field} must be a string or null")
        summary_value = row.summary_value
        if isinstance(summary_value, (bool, np.bool_)) or (
            not isinstance(summary_value, Real) and not _is_missing_scalar(summary_value)
        ):
            raise ValueError(f"{context}: summary_value must be a real scalar or missing")

        # Re-derive rather than trust caller-provided source, band, and date.
        source, dayobs, date = _parse_run_name(row.run_name, pattern)
        for field, expected in (
            ("visit_source", source),
            ("dayobs", dayobs),
            ("band", _band_from_label(row.metric_info_label, source)),
        ):
            if getattr(row, field) != expected:
                raise ValueError(f"{context}: {field} must equal {expected!r}")
        if not isinstance(row.date, (datetime, pd.Timestamp, np.datetime64)) or _is_missing_scalar(row.date):
            raise ValueError(f"{context}: date must be a timezone-naive pandas calendar midnight")
        actual_date = pd.Timestamp(row.date)
        if actual_date.tzinfo is not None or actual_date != date:
            raise ValueError(f"{context}: date must be timezone-naive calendar midnight {date}")

        # Mixing slicers or constraints would imply a misleading sequence.
        sequence = tuple(_grouping_key_value(getattr(row, field)) for field in _SEQUENCE_FIELDS)
        slicer_and_constraint = (
            _grouping_key_value(row.slicer_name),
            _grouping_key_value(row.sql_constraint),
        )
        known = slicer_and_constraint_by_sequence.setdefault(sequence, slicer_and_constraint)
        if known != slicer_and_constraint:
            raise ValueError(
                f"{context}: sequence {sequence!r} has multiple slicer_name or sql_constraint values"
            )

        # A newer stat_id must not hide a conflicting rerun. Missing matches
        # missing; otherwise values must be exactly equal (so equal infinities
        # match and finite values never match approximately).
        record = (row.run_name, *sequence)
        if record in value_by_record:
            previous = value_by_record[record]
            if _is_missing_scalar(previous) or _is_missing_scalar(summary_value):
                values_match = _is_missing_scalar(previous) and _is_missing_scalar(summary_value)
            else:
                values_match = previous == summary_value
            if not values_match:
                raise ValueError(
                    f"{context}: conflicting summary_value for {record!r}: {previous!r} vs {summary_value!r}"
                )
            if not allow_duplicates:
                raise ValueError(f"{context}: duplicate summary record {record!r}")
        value_by_record[record] = summary_value


def load_summary_metrics(db_path: str | Path, *, reference_sim_tag: str = "baseline") -> SummaryMetrics:
    """Read a MAF SQLite database, returning deterministic validated records.

    The database is opened read-only and never created. Only exact supported
    run names are retained, with a warning counting excluded joined summary
    records. Impossible dates and absent schema fail with source context.
    Repeated logical records must have exactly equal finite values, both be
    missing/NaN, or share the same signed infinity. The highest ``stat_id``
    retains its associated provenance. Retained missing/non-finite measurements
    are preserved and counted in a warning, not converted to zero or JSON null.
    Returned numeric columns use int64 for metric_id, stat_id, and dayobs, and
    float64 for summary_value (SQL NULL becomes NaN), including empty results.

    ``reference_sim_tag`` selects the one literal, case-sensitive reference
    source prefix, default ``"baseline"``. An alternate replaces baseline;
    baseline runs are then excluded without date or record validation. Original
    source names and labels are retained. Invalid tags raise ``ValueError``.
    """
    _validate_reference_sim_tag(reference_sim_tag)
    pattern = re.compile(rf"(chimera|consdb|{re.escape(reference_sim_tag)})_([0-9]{{8}})")
    path = Path(db_path).expanduser().resolve()

    # Read every metrics/summarystats join row, read-only so no DB is created.
    # Fail on absent schema before the join. Values stay objects so SQL NULL
    # labels are not replaced by inferred string dtypes.
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
            for table, columns in _REQUIRED_DB_COLUMNS.items():
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
            frame = pd.DataFrame(
                cursor.fetchall(), columns=[item[0] for item in cursor.description], dtype=object
            )
    except (sqlite3.Error, pd.errors.DatabaseError, OSError) as exc:
        raise ValueError(f"Cannot read summary metrics database {path}: {exc}") from exc

    # Keep only supported run names, counting exclusions without validating
    # unrelated runs' other fields.
    is_supported = frame.run_name.map(
        lambda name: isinstance(name, str) and pattern.fullmatch(name) is not None
    ).astype(bool)
    excluded = int((~is_supported).sum())
    if excluded:
        warnings.warn(
            f"Database {path}: excluded {excluded} joined summary records with unsupported run_name",
            UserWarning,
            stacklevel=2,
        )
    frame = frame.loc[is_supported].copy()

    try:
        # Derive source, dayobs, date, and band. Milliseconds match the
        # browser contract without requiring pandas nanosecond storage.
        parsed = [_parse_run_name(name, pattern) for name in frame.run_name]
        frame["visit_source"] = [source for source, _, _ in parsed]
        frame["dayobs"] = pd.Series([dayobs for _, dayobs, _ in parsed], index=frame.index, dtype="int64")
        frame["date"] = pd.Series([date for _, _, date in parsed], index=frame.index, dtype="datetime64[ms]")
        frame["band"] = [
            _band_from_label(label, source)
            for label, source in zip(frame.metric_info_label, frame.visit_source)
        ]
        frame = frame.loc[:, SUMMARY_COLUMNS]

        # Validate all reruns before retaining the highest-stat provenance.
        validate_summary_metrics(frame, reference_sim_tag=reference_sim_tag, allow_duplicates=True)

        # Collapse reruns of each logical record to the highest stat_id,
        # keeping row order. Positions are row positions, not DataFrame index.
        position_by_record: dict[tuple[object, ...], int] = {}
        for position, row in enumerate(frame.itertuples(index=False)):
            record = tuple(_grouping_key_value(getattr(row, field)) for field in _RECORD_FIELDS)
            previous = position_by_record.get(record)
            if previous is None or row.stat_id > frame.iloc[previous].stat_id:
                position_by_record[record] = position
        frame = frame.iloc[sorted(position_by_record.values())].reset_index(drop=True)

        # Cast only validated, deduplicated values; preserve exact ID ordering
        # and duplicate comparisons before normalizing SQL NULL scalars to NaN.
        frame = frame.astype({"metric_id": "int64", "stat_id": "int64", "summary_value": "float64"})
        validate_summary_metrics(frame, reference_sim_tag=reference_sim_tag)
    except ValueError as exc:
        raise ValueError(f"Database {path}: {exc}") from exc

    # Preserve gaps here (plotting/export decides how to encode them), but
    # report their counts.
    missing_count = sum(_is_missing_scalar(value) for value in frame.summary_value)
    nonfinite_count = sum(
        not _is_missing_scalar(value) and not np.isfinite(value) for value in frame.summary_value
    )
    if missing_count or nonfinite_count:
        warnings.warn(
            f"Database {path}: retained {missing_count + nonfinite_count} "
            "missing/non-finite summary measurements "
            f"({missing_count} missing, {nonfinite_count} non-finite)",
            UserWarning,
            stacklevel=2,
        )
    return frame
