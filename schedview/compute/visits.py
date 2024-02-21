import datetime

import numpy as np
from astropy.time import Time

import schedview.compute


def add_day_obs(visits):
    """Add day_obs columns to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFRame with additonal columns: day_obs_date,
        day_obs_mjd, and day_obs_iso8601.
    """
    day_obs_mjd = np.floor(visits["observationStartMJD"] - 0.5).astype("int")
    day_obs_datetime = Time(day_obs_mjd, format="mjd").datetime
    day_obs_date = [datetime.date(t.year, t.month, t.day) for t in day_obs_datetime]
    day_obs_iso8601 = tuple(str(d) for d in day_obs_date)
    visits.insert(1, "day_obs_mjd", day_obs_mjd)
    visits.insert(2, "day_obs_date", day_obs_date)
    visits.insert(3, "day_obs_iso8601", day_obs_iso8601)
    return visits


def add_coords_tuple(visits):
    """Add a coord tuple to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFrame with a 'coords' column that has an RA, dec tuple
    """
    coord_column = max(tuple(visits.columns).index("fieldRA"), tuple(visits.columns).index("fieldDec")) + 1
    visits.insert(coord_column, "coords", list(zip(visits["fieldRA"], visits["fieldDec"])))
    return visits


def add_maf_metric(visits, metric, column_name, visit_resource_path, constraint=None, nighbor_column=None):
    """Add a t_eff column to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns
    `metric` : `rubin_sim.maf.metrics.BaseMetric`
        The metric to compute.
    `column_name` : `str`
        The name for the column with the metric value.
    `visits_resource_path` : `lsst.resources.ResourcePath`
        The location of the resources database.
    `constraint` : `str`
        The conditions used to load the visits.

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFrame with a t_eff column.
    """
    if nighbor_column is None:
        col_index = len(visits.columns)
    else:
        col_index = tuple(visits.columns).index(nighbor_column)

    value = schedview.compute.compute_metric_by_visit(visit_resource_path, metric, constraint)
    visits.insert(col_index, column_name, value)
    return visits


def add_overhead(visits):
    """Add columns with overhead between exposures to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFRame with additonal columns: overhead (in seconds)
        and previous_filter.
    """
    overhead = (
        visits["observationStartMJD"].diff() * 24 * 60 * 60
        - visits["visitTime"].shift(1)
        + visits["visitTime"]
        - visits["visitExposureTime"]
    )
    slew_time_col_index = tuple(visits.columns).index("slewTime")
    visits.insert(slew_time_col_index + 1, "overhead", overhead)

    filter_col_index = tuple(visits.columns).index("filter")
    previous_filter = visits["filter"].shift(1)
    visits.insert(filter_col_index + 1, "previous_filter", previous_filter)
    return visits
