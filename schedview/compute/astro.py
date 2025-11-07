import datetime
from functools import cache

import numpy as np
import pandas as pd
import pytz
from astropy.time import Time
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.site_models.almanac import Almanac
from rubin_scheduler.skybrightness_pre import SkyModelPre

from schedview.dayobs import DayObs


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
        site = ModelObservatory(no_sky=True).location

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

    # We need to use masked_invalid before passing mjds to Time
    # because there are occasional nights where the moon either
    # doesn't rise or doesn't set.
    ap_times = Time(np.ma.masked_invalid(mjds), format="mjd", scale="utc", location=site)
    time_df = pd.DataFrame(
        {
            "MJD": ap_times.mjd,
            "LST": ap_times.sidereal_time("apparent").deg,
            "UTC": pd.to_datetime(ap_times.to_datetime()).tz_localize("UTC"),
        },
        index=mjds.index,
    )
    # If a value is masked, indicate so by a NaN or NaT
    time_df.loc[ap_times.mask, "MJD"] = np.nan
    time_df.loc[ap_times.mask, "UTC"] = np.nan

    time_df[timezone] = time_df["UTC"].dt.tz_convert(timezone)
    time_df.index.name = "event"

    return time_df


def compute_central_night(visits, site=None, timezone="Chile/Continental"):
    """Compute the central night of a set of visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        A DataFrame of visits.
    site : `astropy.coordinates.earth.EarthLocation`
        The observatory location. Defaults to Rubin observatory.
    timezone: `str`
        The timezone name. Defaults to 'Chile/Continental'

    Returns
    -------
    central_night : `datetime.date`
        The central night of the visits.
    """
    central_mjd = visits["observationStartMJD"].median()
    candidate_night = Time(central_mjd, format="mjd", scale="utc").datetime.date()

    # The mjd rollover can occur during the night, so the above might be offset
    # by a night. Make sure the night we have is the one with a central mjd
    # closest to the median visit mjd.
    candidate_middle_mjd = night_events(candidate_night, site, timezone).loc["night_middle", "MJD"]
    mjd_shift = np.round(central_mjd - candidate_middle_mjd)
    central_night = Time(central_mjd + mjd_shift, format="mjd", scale="utc").datetime.date()

    return central_night


def compute_sun_moon_positions(observatory: ModelObservatory) -> pd.DataFrame:
    """Create a DataFrame of sun and moon positions with one row per body,
    one column per coordinate, at the time set for the observatory.

    Parameters
    ----------
    observatory : `ModelObservatory`
        The model observatory.

    Returns
    -------
    body_positions : `pandas.DataFrame`
        The table of body positions.
    """
    body_positions_wide = pd.DataFrame(observatory.almanac.get_sun_moon_positions(observatory.mjd))

    body_positions_wide.index.name = "r"
    body_positions_wide.reset_index(inplace=True)

    angle_columns = ["RA", "dec", "alt", "az"]
    all_columns = angle_columns + ["phase"]
    body_positions = (
        pd.wide_to_long(
            body_positions_wide,
            stubnames=("sun", "moon"),
            suffix=r".*",
            sep="_",
            i="r",
            j="coordinate",
        )
        .droplevel("r")
        .T[all_columns]
    )
    body_positions[angle_columns] = np.degrees(body_positions[angle_columns])
    return body_positions


def get_median_model_sky(day_obs: DayObs, bands: tuple[str] = ("u", "g", "r", "i", "z", "y")) -> pd.DataFrame:
    """Get model sky and ephemeris values suitable for a timeline plot.

    Parameters
    ----------
    day_obs : `DayObs`
        The day of observing.
    bands : `tuple`, optional
        Bands to get sky values for, by default ("u", "g", "r", "i", "z", "y")

    Returns
    -------
    median_model_sky : `pd.DataFrame`
        A pandas.DataFrame with the median model sky values and sun and moon
        parameters.
    """
    sky_model = SkyModelPre(mjd0=day_obs.start.mjd, load_length=1)
    mjds = sky_model.mjds

    whole_day_obs = pd.DataFrame(Almanac().get_sun_moon_positions(mjds), index=pd.Index(mjds, name="mjd"))

    for band in bands:
        whole_day_obs[band] = np.nanmedian(np.array(sky_model.sb[band]), axis=1)

    # Get edges of span over which the sample can be plotted
    sample_mjds = mjds[1:-1]
    prior_mjds = mjds[:-2]
    next_mjds = mjds[2:]

    # Use day_obs to get the times of night.
    # We cannot use the sun alt we get from the almanac, because
    # the sun from the prior night does not reach alt=0 until after
    # the day_obs rollover, and so doing this will give one or more
    # points from the prior night.
    night_mjds = sample_mjds[(prior_mjds > day_obs.sunset.mjd) & (next_mjds < day_obs.sunrise.mjd)]
    whole_day_obs.loc[sample_mjds, "begin_time"] = Time(
        (sample_mjds + prior_mjds) / 2, format="mjd"
    ).datetime64
    whole_day_obs.loc[sample_mjds, "time"] = Time(sample_mjds, format="mjd").datetime64
    whole_day_obs.loc[sample_mjds, "end_time"] = Time((sample_mjds + next_mjds) / 2, format="mjd").datetime64

    result_columns = ["time", "begin_time", "end_time"] + list(bands) + ["sun_alt", "moon_alt", "moon_phase"]

    night = whole_day_obs.loc[night_mjds, result_columns]
    night["sun_alt"] = np.degrees(night["sun_alt"])
    night["moon_alt"] = np.degrees(night["moon_alt"])
    return night
