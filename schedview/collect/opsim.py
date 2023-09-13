import sqlite3

import numpy as np
import pandas as pd
from astropy.time import Time


def read_opsim(filename, start_time="2000-01-01", end_time="2100-01-01"):
    """Read visits from an opsim database.

    Parameters
    ----------
    filename : `str`
        The file from which to load visits
    start_time : `str`, `astropy.time.Time`
        The start time for visits to be loaded
    end_time : `str`, `astropy.time.Time`
        The end time for visits ot be loaded

    Returns
    -------
    visits : `pandas.DataFrame`
        The visits and their parameters.
    """
    start_mjd = Time(start_time).mjd
    end_mjd = Time(end_time).mjd

    with sqlite3.connect(filename) as sim_connection:
        visits = pd.read_sql_query(
            f"SELECT * FROM observations WHERE observationStartMJD BETWEEN {start_mjd} AND {end_mjd}",
            sim_connection,
            index_col="observationId",
        )

    visits["start_date"] = pd.to_datetime(
        visits["observationStartMJD"] + 2400000.5, origin="julian", unit="D", utc=True
    )

    if "HA_hours" not in visits.columns:
        visits["HA_hours"] = (visits.observationStartLST - visits.fieldRA) * 24.0 / 360.0
        visits["HA_hours"] = np.mod(visits["HA_hours"] + 12.0, 24) - 12

    return visits
