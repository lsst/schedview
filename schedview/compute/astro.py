import datetime
from functools import cache

import numpy as np
import pandas as pd
import pytz
from astropy.time import Time
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.site_models.almanac import Almanac


@cache
def _compute_all_night_events():
    # Loading the alamac takes a while, so generate it with a function
    # that caches the result (using the functools.cache decorator).
    almanac = Almanac()
    all_nights_events = pd.DataFrame(almanac.sunsets)
    all_nights_events["night_middle"] = (all_nights_events["sunrise"] + all_nights_events["sunset"]) / 2
    return all_nights_events


@cache
def convert_evening_date_to_night_of_survey(night_date, timezone="Chile/Continental"):
    """Convert a calendar date in the evening to the night of survey.

    Parameters
    ----------
    night_date : `datetime.date`
        The calendar date in the evening local time.
    timezone: `str`
        The string designating the time zone. Defaults to 'Chile/Continental'

    Returns
    -------
    night_of_survey : `int`
        The night of survey, starting from 0.
    """
    sample_time = Time(
        pytz.timezone(timezone)
        .localize(datetime.datetime(night_date.year, night_date.month, night_date.day, 23, 59, 59))
        .astimezone(pytz.timezone("UTC"))
    )
    all_nights_events = _compute_all_night_events()
    closest_middle_iloc = np.abs(sample_time.mjd - all_nights_events["night_middle"]).argsort()[0]
    night_of_survey = all_nights_events.iloc[closest_middle_iloc, :]["night"]
    return night_of_survey


def night_events(night_date=None, site=None, timezone="Chile/Continental"):
    """Creata a pandas.DataFrame with astronomical events.

    Parameters
    ----------
    night_date : `datetime.date`
        The calendar date in the evening local time.
    site : `astropy.coordinates.earth.EarthLocation`
        The observatory location. Defaults to Rubin observatory.
    timezone: `str`
        The timezone name. Defaults to 'Chile/Continental'

    Returns
    -------
    events : `pandas.DataFrame`
        A DataFrame of night events.
    """
    if night_date is None:
        night_date = datetime.date.today()

    if site is None:
        site = ModelObservatory().location

    all_nights_events = _compute_all_night_events().set_index("night")
    night_of_survey = convert_evening_date_to_night_of_survey(night_date, timezone=timezone)
    mjds = all_nights_events.loc[night_of_survey]

    # Not all night have both a moon rise and moon set. If a night is missing
    # one, use the value from the following night or prior night, whichever
    # is closer to night_middle
    for event in mjds.index:
        if mjds[event] <= 0:
            next_night = night_of_survey + 1
            prior_night = night_of_survey - 1
            night_middle = mjds["night_middle"]
            next_dt = np.abs(all_nights_events.loc[next_night, event] - night_middle)
            proir_dt = np.abs(all_nights_events.loc[prior_night, event] - night_middle)
            closest_night = next_night if next_dt < proir_dt else prior_night
            mjds[event] = all_nights_events.loc[closest_night, event]

    ap_times = Time(mjds, format="mjd", scale="utc", location=site)
    time_df = pd.DataFrame(
        {
            "MJD": ap_times.mjd,
            "LST": ap_times.sidereal_time("apparent").deg,
            "UTC": pd.to_datetime(ap_times.iso).tz_localize("UTC"),
        },
        index=mjds.index,
    )
    time_df[timezone] = time_df["UTC"].dt.tz_convert(timezone)
    time_df.index.name = "event"

    return time_df
