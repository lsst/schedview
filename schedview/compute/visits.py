import datetime

import numpy as np
from astropy.time import Time


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
