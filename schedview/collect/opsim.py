import sqlite3

import pandas as pd
import yaml
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_scheduler.utils import ddf_locations

try:
    from rubin_sim import maf
except ModuleNotFoundError:
    pass

DEFAULT_VISITS_COLUMNS = [
    "observationId",
    "fieldRA",
    "fieldDec",
    "observationStartMJD",
    "flush_by_mjd",
    "visitExposureTime",
    "filter",
    "rotSkyPos",
    "rotSkyPos_desired",
    "numExposures",
    "airmass",
    "seeingFwhm500",
    "seeingFwhmEff",
    "seeingFwhmGeom",
    "skyBrightness",
    "night",
    "slewTime",
    "visitTime",
    "slewDistance",
    "fiveSigmaDepth",
    "altitude",
    "azimuth",
    "paraAngle",
    "cloud",
    "moonAlt",
    "sunAlt",
    "note",
    "target",
    "fieldId",
    "proposalId",
    "block_id",
    "observationStartLST",
    "rotTelPos",
    "rotTelPos_backup",
    "moonAz",
    "sunAz",
    "sunRA",
    "sunDec",
    "moonRA",
    "moonDec",
    "moonDistance",
    "solarElong",
    "moonPhase",
    "cummTelAz",
    "scripted_id",
]


def read_opsim(
    opsim_uri,
    start_time=None,
    end_time=None,
    constraint=None,
    dbcols=DEFAULT_VISITS_COLUMNS,
    **kwargs,
):
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
    dbcols : `list` [`str`]
        Columns required from the database.
    **kwargs
        Passed to `maf.get_sim_data`, if `rubin_sim` is available.

    Returns
    -------
    visits : `pandas.DataFrame`
        The visits and their parameters.
    """

    # Add constraints corresponding to quested start and end times
    if (start_time is not None) or (end_time is not None):
        if constraint is None:
            constraint = ""

        if start_time is not None:
            if len(constraint) > 0:
                constraint += " AND "
            constraint += f"(observationStartMJD >= {Time(start_time).mjd})"

        if end_time is not None:
            if len(constraint) > 0:
                constraint += " AND "
            constraint += f"(observationStartMJD <= {Time(end_time).mjd})"

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
            try:
                visits = pd.DataFrame(maf.get_sim_data(sim_connection, constraint, dbcols, **kwargs))
            except NameError as e:
                if e.name == "maf" and e.args == ("name 'maf' is not defined",):
                    if len(kwargs) > 0:
                        raise NotImplementedError(
                            f"Argument {list(kwargs)[0]} not supported without rubin_sim installed"
                        )

                    query = f'SELECT {", ".join(dbcols)} FROM observations'
                    if constraint:
                        query += f" WHERE {constraint}"
                    visits = pd.read_sql(query, sim_connection)
                else:
                    raise e

    if "observationStartDatetime64" in visits:
        visits["start_date"] = pd.to_datetime(visits.observationStartDatetime64, unit="ns", utc=True)

    visits.set_index("observationId", inplace=True)

    return visits


def read_ddf_visits(
    opsim_uri,
    start_time=None,
    end_time=None,
    dbcols=DEFAULT_VISITS_COLUMNS,
    **kwargs,
):
    """Read DDF visits from an opsim database.

    Parameters
    ----------
    opsim_uri : `str`
        The uri from which to load visits
    start_time : `str`, `astropy.time.Time`
        The start time for visits to be loaded
    end_time : `str`, `astropy.time.Time`
        The end time for visits ot be loaded
    dbcols : `list` [`str`]
        Columns required from the database.
    stackers : `list` [`rubin_sim.maf.stackers`], optional
        Stackers to be used to generate additional columns.

    Returns
    -------
    visits : `pandas.DataFrame`
        The visits and their parameters.
    """
    ddf_field_names = tuple(ddf_locations().keys())
    constraint = f"target IN {tuple(field_name for field_name in ddf_field_names)}"
    visits = read_opsim(
        opsim_uri,
        start_time=start_time,
        end_time=end_time,
        constraint=constraint,
        dbcols=dbcols,
        **kwargs,
    )
    return visits
