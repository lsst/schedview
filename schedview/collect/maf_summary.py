"""Load MAF summary metrics from a ResultsDb SQLite database."""

__all__ = ["load_maf_summary"]

import logging
import re
import sqlite3
from datetime import datetime

import pandas as pd

_logger = logging.getLogger(__name__)

# Matches an 8-digit date (YYYYMMDD) at the end of a string,
# optionally preceded by an underscore.
_DATE_PATTERN = re.compile(r"_?(\d{8})$")


def _extract_transition_date(run_name: str):
    """Extract a transition date from a run_name string.

    Looks for an 8-digit YYYYMMDD pattern at the end of
    ``run_name``. Returns a ``datetime.date`` on success, or
    ``None`` if the pattern is not found or is not a valid date.

    Parameters
    ----------
    run_name : `str`
        The run name to parse (e.g. ``"chimera_20251031"``).

    Returns
    -------
    date : `datetime.date` or ``None``
        The extracted date, or ``None`` if parsing fails.
    """
    match = _DATE_PATTERN.search(run_name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def load_maf_summary(
    db_path: str,
    run_name_pattern: str = "chimera_%",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and preprocess MAF summary data from a ResultsDb database.

    Queries the database for all runs matching ``run_name_pattern`` and
    returns a DataFrame with one row per metric per run, plus a
    deduplicated DataFrame of unique metric labels for selector
    dropdowns.

    Parameters
    ----------
    db_path : `str`
        Path to the resultsDb_sqlite.db file.
    run_name_pattern : `str`, optional
        SQL LIKE pattern to filter ``run_name`` values.  Defaults to
        ``"chimera_%"`` to select chimera runs.

    Returns
    -------
    summary_df : `pandas.DataFrame`
        DataFrame with columns: run_name, metric_name, slicer_name,
        metric_info_label, summary_metric, summary_value,
        transition_dayobs, transition_date.
    unique_metrics : `pandas.DataFrame`
        Deduplicated and sorted DataFrame of unique (metric_name,
        slicer_name, metric_info_label, summary_metric) combinations.

    Raises
    ------
    sqlite3.OperationalError
        If the database file does not exist or cannot be opened.
    ValueError
        If no rows have parseable transition dates.
    """
    conn = sqlite3.connect(db_path)
    query = """
    SELECT
        m.run_name,
        m.metric_name,
        m.slicer_name,
        m.metric_info_label,
        ss.summary_name AS summary_metric,
        ss.summary_value
    FROM metrics m
    JOIN summarystats ss ON m.metric_id = ss.metric_id
    WHERE m.run_name LIKE ?
    ORDER BY m.run_name, m.metric_name, m.slicer_name,
             m.metric_info_label, ss.summary_name
    """
    df = pd.read_sql_query(query, conn, params=(run_name_pattern,))
    conn.close()

    # Extract transition_date from run_name.
    # For "chimera_20251031" this yields date(2025, 10, 31).
    df["transition_date"] = df["run_name"].apply(
        _extract_transition_date
    )

    # Drop rows where the date could not be parsed and warn.
    n_bad = df["transition_date"].isna().sum()
    if n_bad > 0:
        bad_names = df.loc[
            df["transition_date"].isna(), "run_name"
        ].unique()
        _logger.warning(
            "Dropped %d rows with unparseable run_name dates: %s",
            n_bad,
            list(bad_names[:5]),
        )
        df = df.dropna(subset=["transition_date"]).reset_index(
            drop=True
        )

    if len(df) == 0:
        raise ValueError(
            "No rows with parseable transition dates found for "
            f"run_name_pattern={run_name_pattern!r}."
        )

    # Derive integer day_obs from the parsed date.
    df["transition_dayobs"] = df["transition_date"].apply(
        lambda d: int(d.strftime("%Y%m%d"))
    )

    # Deduplicated unique metrics for dropdown options
    unique_metrics = (
        df.drop_duplicates(
            subset=[
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        )
        .sort_values(
            [
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        )
        .reset_index(drop=True)
    )

    return df, unique_metrics
