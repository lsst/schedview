import datetime
from typing import Literal

from schedview.collect import get_from_logdb_with_retries
from schedview.dayobs import DayObs

EXCLUDED_COMPONENTS_FOR_TELESCOPE = {
    "AuxTel": ["MTMount", "MainTel"],
    "Simonyi": ["AuxTel", "ATMCS", "ATDome"],
}


def get_night_report(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"],
    user_params: dict | None = None,
) -> list[dict]:
    """Get the night report data for a night of observing.

    Parameters
    ----------
    day_obs: `DayObs` | `str` | `int`
        The night of observation.
    telescope : `str``
        The telescope for which to get the night report.
    user_params : `dict` | None, optional
        Extra parameters for the night report query

    Returns
    -------
    night_reports : `list[dict]`
        A list of dictionaries with every version of the night report for
        the requested night.
    """

    day_obs = DayObs.from_date(day_obs)

    params = {
        "telescopes": telescope,
        "min_day_obs": day_obs.yyyymmdd,
        "max_day_obs": DayObs.from_date(day_obs.date + datetime.timedelta(days=1)).yyyymmdd,
        "is_valid": "true",
    }
    if user_params is not None:
        params.update(user_params)

    result = get_from_logdb_with_retries(channel="nightreport/reports", params=params)
    return result


def get_night_narrative(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"] | None,
    night_only: bool = True,
    user_params: dict | None = None,
) -> list[dict]:
    """Get the log messages for a given dayobs.

    Parameters
    ----------
    day_obs: `DayObs` | `str` | `int`
        The night of observation.
    telescope : `str`` | ``None``
        The telescope for which to get the night report.
    night_only: `bool` optional
        Include only messages between sunset and sunrise, by default True.
    user_params : `dict` | None, optional
        Extra parameters for the narrativelog query

    Returns
    -------
    messages : `list[dict]`
        A list of dictionaries with log messages.
    """

    day_obs = DayObs.from_date(day_obs)

    if night_only:
        min_date_begin_time = day_obs.sunset
        max_date_begin_time = day_obs.sunrise
    else:
        min_date_begin_time = day_obs.start
        max_date_begin_time = day_obs.end

    params = {
        "is_human": "either",
        "is_valid": "true",
        "has_date_begin": True,
        "min_date_begin": min_date_begin_time.to_datetime(),
        "max_date_begin": max_date_begin_time.to_datetime(),
        "order_by": "date_begin",
    }

    if telescope is not None:
        params["exclude_components"] = EXCLUDED_COMPONENTS_FOR_TELESCOPE[telescope]

    if user_params is not None:
        params.update(user_params)

    result = get_from_logdb_with_retries(channel="narrativelog/messages", params=params)
    return result
