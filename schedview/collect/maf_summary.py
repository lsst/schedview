"""Load MAF summary metrics from a ResultsDb SQLite database."""

__all__ = ["load_maf_summary"]

import sqlite3
from datetime import datetime

import pandas as pd


def load_maf_summary(
    db_path: str,
    run_name_pattern: str = "chimera_%",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and preprocess MAF summary data from a ResultsDb database.

    Queries the database for all runs matching ``run_name_pattern`` and
    returns a DataFrame with one row per metric per run, plus a
    deduplicated DataFrame of unique metric labels for selector dropdowns.

    Parameters
    ----------
    db_path : str
        Path to the resultsDb_sqlite.db file.
    run_name_pattern : str, optional
        SQL LIKE pattern to filter ``run_name`` values.  Defaults to
        ``"chimera_%"`` to select chimera runs.

    Returns
    -------
    summary_df : pd.DataFrame
        DataFrame with columns: run_name, metric_name, slicer_name,
        metric_info_label, summary_metric, summary_value,
        transition_dayobs, transition_date.
    unique_metrics : pd.DataFrame
        Deduplicated and sorted DataFrame of unique (metric_name,
        slicer_name, metric_info_label, summary_metric) combinations.

    Raises
    ------
    sqlite3.OperationalError
        If the database file does not exist or cannot be opened.
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

    # Extract transition_dayobs from run_name.
    # For "chimera_20251031" this yields 20251031.
    # Uses the portion after the last underscore.
    df["transition_dayobs"] = df["run_name"].apply(
        lambda x: int(x.rsplit("_", 1)[1])
    )
    df["transition_date"] = df["transition_dayobs"].apply(
        lambda d: datetime.strptime(str(d), "%Y%m%d").date()
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
            ["metric_name", "slicer_name", "metric_info_label", "summary_metric"]
        )
        .reset_index(drop=True)
    )

    return df, unique_metrics
