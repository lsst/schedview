import sqlite3
from warnings import warn

import pandas as pd
import rubin_scheduler
import yaml
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_scheduler.scheduler.utils import SchemaConverter
from rubin_scheduler.utils import ddf_locations

try:
    from rubin_sim import maf
except ModuleNotFoundError:
    pass


def all_visits_columns():
    """Return all visits columns understood by the current rubin_scheduler."""
    schema_converter = SchemaConverter()
    current_cols = set(schema_converter.convert_dict.keys())
    backwards_cols = set(schema_converter.backwards.keys())
    return current_cols.union(backwards_cols)


def _normalize_opsim_columns(opsim_rp: ResourcePath, dbcols: list[str]):
    # At least one opsim column has been renamed since the start of
    # simulations. The mapping between new and old names can be found in
    # rubin_scheduler.scheduler.utils.SchemaConverter.backwards.

    # We want our queries to work the same whether run on simulation from
    # before or after the name change. So, if a requested column is missing,
    # see if it is the renamed value of one that used to exist, and if so,
    # use the old column name instead.

    # In addition to returning the list of columns with the replaced column
    # name, return the mapping so that a table's column headings can be
    # updated from the old name used to the new (requested) name.

    with opsim_rp.as_local() as local_obs_path:
        with sqlite3.connect(local_obs_path.ospath) as sim_connection:
            query = "SELECT name FROM PRAGMA_TABLE_INFO('observations');"
            present_columns = set(pd.read_sql(query, sim_connection).name.values)

    new_columns = []
    used_column_map = {}
    backwards_column_map = {v: k for k, v in SchemaConverter().backwards.items()}
    for column in dbcols:
        if column in present_columns:
            new_columns.append(column)
        elif column in backwards_column_map:
            old_column = backwards_column_map[column]
            if old_column in present_columns:
                warn(f"Column {column} not found in {opsim_rp}, using deprecated {old_column} instead")
                used_column_map[old_column] = column
                new_columns.append(old_column)
            else:
                warn(f"Neither column {column} nor deprecated {old_column} found in {opsim_rp}, skipping.")
        else:
            warn(f"Column {column} not found in {opsim_rp}, skipping.")

    return new_columns, used_column_map


def read_opsim(
    opsim_uri,
    start_time=None,
    end_time=None,
    constraint=None,
    dbcols=None,
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
    dbcols : `None` or `list` [`str`]
        Columns required from the database. Defaults to None, which queries
        all columns known to rubin_scheduler.
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
            if dbcols is None:
                col_query = "SELECT name FROM PRAGMA_TABLE_INFO('observations')"
                raw_dbcols = [
                    c for c in pd.read_sql(col_query, sim_connection).name if c in all_visits_columns()
                ]

                # Update any outdated column names
                backwards = SchemaConverter().backwards
                dbcols = [(backwards[c] if c in backwards else c) for c in raw_dbcols]

            norm_columns, used_column_map = _normalize_opsim_columns(obs_path, dbcols)

            try:
                try:
                    visits = pd.DataFrame(
                        maf.get_sim_data(sim_connection, constraint, norm_columns, **kwargs)
                    )
                except UserWarning:
                    warn("No visits match constraints.")
                    visits = (
                        SchemaConverter()
                        .obs2opsim(rubin_scheduler.scheduler.utils.ObservationArray())
                        .iloc[0:-1]
                    )
                    if "observationId" not in visits.columns and "ID" in visits.columns:
                        visits.rename(columns={"ID": "observationId"}, inplace=True)
            except NameError as e:
                if e.name == "maf" and e.args == ("name 'maf' is not defined",):
                    if len(kwargs) > 0:
                        raise NotImplementedError(
                            f"Argument {list(kwargs)[0]} not supported without rubin_sim installed"
                        )

                    query = f'SELECT {", ".join(norm_columns)} FROM observations'
                    if constraint:
                        query += f" WHERE {constraint}"
                    visits = pd.read_sql(query, sim_connection)
                else:
                    raise e

            # If we replaced modern columns with legacy ones in the query,
            # update the column names.
            visits.rename(columns=used_column_map, inplace=True)

            if "start_date" not in visits:
                if "observationStartDatetime64" in visits:
                    visits["start_date"] = pd.to_datetime(
                        visits.observationStartDatetime64, unit="ns", utc=True
                    )
                elif "observationStartMJD" in visits:
                    visits["start_date"] = pd.to_datetime(
                        visits.observationStartMJD + 2400000.5, origin="julian", unit="D", utc=True
                    )

    visits.set_index("observationId", inplace=True)

    return visits


def read_ddf_visits(
    opsim_uri,
    start_time=None,
    end_time=None,
    dbcols=None,
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
    dbcols : `Note` oc `list` [`str`]
        Columns required from the database. Defaults to None,
        which uses all columns in the database.
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
