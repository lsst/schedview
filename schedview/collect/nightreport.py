import datetime
from typing import Literal

import requests

from schedview.dayobs import DayObs

from .efd import ClientConnections

MAX_RETRIES = 2

EXCLUDED_COMPONENTS_FOR_TELESCOPE = {
    "AuxTel": ["MTMount", "MainTel"],
    "Simonyi": ["AuxTel", "ATMCS", "ATDome"],
}


def _get_with_retries(api_endpoint, auth, params):
    response = requests.get(api_endpoint, auth=auth, params=params)
    try_number = 1
    while not response.status_code == 200:
        if try_number > MAX_RETRIES:
            response.raise_for_status()
        response = requests.get(api_endpoint, auth=auth, params=params)
        try_number += 1

    return response.json()


def get_night_report(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"],
    user_client_connections: ClientConnections | None = None,
    user_params: dict | None = None,
) -> list[dict]:
    """Get the night report data for a night of observing.

    Parameters
    ----------
    day_obs: `DayObs` | `str` | `int`
        The night of observation.
    telescope : `str``
        The telescope for which to get the night report.
    user_client_connections : `ClientConnections` | None, optional
        The connections to the EFD and other services or None to infer
        them from the environment. Defaults to None.
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

    client_connection: ClientConnections = (
        ClientConnections() if user_client_connections is None else user_client_connections
    )

    assert isinstance(client_connection.base, str)
    api_endpoint = "".join([client_connection.base, "nightreport/reports"])
    return _get_with_retries(api_endpoint, auth=client_connection.auth, params=params)


def get_night_narrative(
    day_obs: DayObs | str | int,
    telescope: Literal["AuxTel", "Simonyi"],
    night_only: bool = True,
    user_client_connections: ClientConnections | None = None,
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
    user_client_connections : `ClientConnections` | None, optional
        The connections to the EFD and other services or None to infer
        them from the environment. Defaults to None.
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

    client_connection: ClientConnections = (
        ClientConnections() if user_client_connections is None else user_client_connections
    )

    assert isinstance(client_connection.base, str)
    api_endpoint = "".join([client_connection.base, "narrativelog/messages"])
    return _get_with_retries(api_endpoint, auth=client_connection.auth, params=params)
