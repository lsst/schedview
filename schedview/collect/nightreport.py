import datetime
from typing import Literal

import requests

from schedview.dayobs import DayObs

MAX_RETRIES = 2

EXCLUDED_COMPONENTS_FOR_TELESCOPE = {
    "AuxTel": ["MTMount", "MainTel"],
    "Simonyi": ["AuxTel", "ATMCS", "ATDome"],
}


def _get_with_retries(api_endpoint, params):
    response = requests.get(api_endpoint, params)
    try_number = 1
    while not response.status_code == 200:
        if try_number > MAX_RETRIES:
            response.raise_for_status()
        response = requests.get(api_endpoint, params)
        try_number += 1

    return response.json()


def get_night_report(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"],
    api_endpoint: str = "https://usdf-rsp-dev.slac.stanford.edu/nightreport/reports",
    user_params: dict | None = None,
) -> list[dict]:
    """Get the night report data for a night of observing.

    Parameters
    ----------
    day_obs: `DayObs` | `str` | `int`
        The night of observation.
    telescope : `str``
        The telescope for which to get the night report.
    api_endpoint : `str`, optional
        The URL for the source fo the night report,
        by default "https://usdf-rsp-dev.slac.stanford.edu/nightreport/reports"
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

    return _get_with_retries(api_endpoint, params)


def get_night_narrative(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"],
    night_only: bool = True,
    api_endpoint: str = "https://usdf-rsp-dev.slac.stanford.edu/narrativelog/messages",
    user_params: dict | None = None,
) -> list[dict]:
    """Get the log messages for a given dayobs.

    Parameters
    ----------
    day_obs: `DayObs` | `str` | `int`
        The night of observation.
    telescope : `str``
        The telescope for which to get the night report.
    night_only: `bool` optional
        Include only messages between sunset and sunrise, by default True.
    api_endpoint : `str`, optional
        The URL for the source fo the night report, by default
        "https://usdf-rsp-dev.slac.stanford.edu/narrativelog/messages"
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
        "exclude_components": EXCLUDED_COMPONENTS_FOR_TELESCOPE[telescope],
        "order_by": "date_begin",
    }

    if user_params is not None:
        params.update(user_params)

    return _get_with_retries(api_endpoint, params)
