import sqlite3

import numpy as np
import pandas as pd
import yaml
from astropy.time import Time
from lsst.resources import ResourcePath


def read_opsim(opsim_uri, start_time="2000-01-01", end_time="2100-01-01", constraint=None):
    """Read visits from an opsim database.

    Parameters
    ----------
    opsim_uri : `str`
        The uri from which to load visits
    start_time : `str`, `astropy.time.Time`
        The start time for visits to be loaded
    end_time : `str`, `astropy.time.Time`
        The end time for visits ot be loaded
    constraint : `str`, None
        Query for which visits to load.

    Returns
    -------
    visits : `pandas.DataFrame`
        The visits and their parameters.
    """
    start_mjd = Time(start_time).mjd
    end_mjd = Time(end_time).mjd
    date_conditions = f"observationStartMJD BETWEEN {start_mjd} AND {end_mjd}"
    constraint = date_conditions if constraint is None else f"{constraint} AND {date_conditions}"

    original_resource_path = ResourcePath(opsim_uri)

    if original_resource_path.isdir():
        # If we were given a directory, look for a metadata file in the
        # directory, and look up in it what file to load observations from.
        metadata_path = original_resource_path.join("sim_metadata.yaml")
        sim_metadata = yaml.safe_load(metadata_path.read().decode("utf-8"))
        obs_basename = sim_metadata["files"]["observations"]["name"]
        obs_path = original_resource_path.join(obs_basename)
    else:
        # otherwise, assume we were given the path to the observations file.
        obs_path = original_resource_path

    with obs_path.as_local() as local_obs_path:
        with sqlite3.connect(local_obs_path.ospath) as sim_connection:
            visits = pd.read_sql_query(
                f"""SELECT * FROM observations WHERE {constraint}""",
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
