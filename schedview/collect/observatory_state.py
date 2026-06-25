import pandas as pd
import rubin_nights.dayobs_utils as rn_dayobs
import rubin_nights.observatory_status as obs_status
from astropy.time import TimeDelta
from rubin_nights.influx_query import InfluxQueryClient

import schedview.clientsite

from .auth import get_auth


def get_observatory_status_summary(day_obs: int, day_obs_max: int | None) -> pd.DataFrame:
    """Return a summary of observatory status (WEATHER, DOWNTIME, etc).

    Parameters
    ----------
    day_obs : `int`
        Day_obs (YYYYMMDD) to start query.
    day_obs_max : `int` or `None`
        Day_obs (YYYYMMDD) to end query. If None, query only the first day_obs.

    Returns
    -------
    obs_status_summary : `pd.DataFrame`
        Dataframe with index `day_obs` and columns including `weather_down`
        indicating the hours of weather downtime during the night.
    """

    # Make some assumptions that ought to work in an RSP environment,
    # or user's env variables match schedview's expectations,
    # e.g. tokenfile set in env variable ACCESS_TOKEN_FILE.
    site = schedview.clientsite.EFD_NAME.replace("_efd", "")
    auth = get_auth()

    # Remind me to come back and make this context manager to ensure close.
    efd_client = InfluxQueryClient(site=site, db_name="efd", repertoire_site=site, auth=auth)

    t_start = rn_dayobs.day_obs_to_time(day_obs)
    if day_obs_max is not None:
        t_end = rn_dayobs.day_obs_to_time(day_obs_max) + TimeDelta(1, format="jd")
    else:
        t_end = t_start + TimeDelta(1, format="jd")
    obs_status_times = obs_status.get_observatory_state_times(t_start, t_end, efd_client=efd_client)
    obs_status_times, obs_status_summary = obs_status.count_observatory_states(
        obs_status_times, dome_open=None
    )

    return obs_status_summary
