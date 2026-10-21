"""Load and preprocess chimera summary data from a ResultsDb database.
"""

import json
import os
import re as re_module

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime


def load_chimera_summary(db_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and preprocess chimera summary data from a ResultsDb database.

    Queries the database for all chimera run metrics and returns a DataFrame
    with one row per metric per transition date.

    Parameters
    ----------
    db_path : str
        Path to the resultsDb_sqlite.db file.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        - DataFrame with columns: transition_dayobs, transition_date, metric_name,
          slicer_name, metric_info_label, summary_metric, summary_value
        - DataFrame of unique metrics for selector dropdowns
    """
    conn = sqlite3.connect(db_path)
    query = '''
    SELECT
        m.run_name,
        m.metric_name,
        m.slicer_name,
        m.metric_info_label,
        ss.summary_name AS summary_metric,
        ss.summary_value
    FROM metrics m
    JOIN summarystats ss ON m.metric_id = ss.metric_id
    WHERE (m.run_name LIKE 'chimera_%'
           OR m.run_name LIKE 'baseline_%'
           OR m.run_name LIKE 'consdb_%')
    ORDER BY m.run_name, m.metric_name, m.slicer_name, m.metric_info_label, ss.summary_name
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Extract transition_dayobs from run_name (e.g., 'chimera_20251031' -> 20251031)
    # dayObs is YYYYMMDD format, convert to proper datetime for plotting
    df['transition_dayobs'] = df['run_name'].apply(
        lambda x: int(re_module.sub(r'^(chimera|baseline|consdb)_', '', x))
    )
    df['transition_date'] = df['transition_dayobs'].apply(
        lambda d: datetime.strptime(str(d), '%Y%m%d').date()
    )

    # Get unique values for each dropdown level
    unique_metrics = df.drop_duplicates(
        subset=['metric_name', 'slicer_name', 'metric_info_label', 'summary_metric']
    ).sort_values(['metric_name', 'slicer_name', 'metric_info_label', 'summary_metric'])

    return df, unique_metrics
