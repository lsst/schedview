import requests

import schedview.clientsite
from schedview.collect.auth import get_auth

MAX_RETRIES = 2


def get_from_logdb_with_retries(channel: str, params: dict) -> list[dict]:
    """Retrieve log messages, with retries.

    Parameters
    ----------
    channel : `str`
        The channel from which to retrieve log messages.
    params : `dict`
        Parameters passed to the REST URI.

    Returns
    -------
    result: `list[dict]`
        The log messages.
    """
    try:
        # Note that get_auth is cached, so it does not actually read the
        # token every time.
        auth = get_auth()
    except ValueError:
        auth = ("user", None)

    api_endpoint = f"{schedview.clientsite.DATASOURCE_BASE_URL}{channel}"
    response = requests.get(api_endpoint, auth=auth, params=params)
    try_number = 1
    while not response.status_code == 200:
        if try_number > MAX_RETRIES:
            response.raise_for_status()
        response = requests.get(api_endpoint, auth=auth, params=params)
        try_number += 1

    return response.json()
