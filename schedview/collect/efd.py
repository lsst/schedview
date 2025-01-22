import asyncio
import os
import threading
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from warnings import warn

import pandas as pd
from lsst_efd_client import EfdClient

from schedview.dayobs import DayObs

try:
    from lsst.rsp import get_access_token
except ImportError:

    def get_access_token(token_file: str | None = None) -> str:
        token = os.environ.get("ACCESS_TOKEN")
        if token is None and token_file is not None:
            with open("token_file", "r") as f:
                token = f.read()

        if not isinstance(token, str):
            raise ValueError("No access token found.")

        return token


SAL_INDEX_GUESSES = defaultdict(partial([[]].__getitem__, 0), {"lsstcomcam": [1, 3], "latiss": [2]})


@dataclass
class ClientConnections:
    base: str | None
    efd: EfdClient
    obsenv: EfdClient
    auth: tuple[str, str]


def get_clients() -> ClientConnections:
    """Return site-specific client connections.

    Returns
    -------
    client_connections : `ClientConnections`
        A named tuple with the following fields:
        - `base` : `str`
            The base URL for the site.
        - `efd` : `EfdClient`
            The EFD client for the site.
        - `obsenv` : `EfdClient`
            The obsenv EFD client for the site.
        - `auth` : `tuple`
            The authentication type and token.
    """
    # Set up authentication
    token = get_access_token()
    auth = ("user", token)
    # This authentication is for nightlog, exposurelog, nightreport currently
    # But I think it's the same underlying info for EfdClient i.e.
    # https://github.com/lsst/schedview/blob/e11fbd51ee5e22d11fef9a52f66dfcc082181cb6/schedview/app/scheduler_dashboard/influxdb_client.py

    # let's do this like lsst.summit.utils.getSite but simpler
    site = "UNKNOWN"
    location = os.getenv("EXTERNAL_INSTANCE_URL", "")
    if "tucson-teststand" in location:
        site = "tucson"
    elif "summit-lsp" in location:
        site = "summit"
    elif "base-lsp" in location:
        site = "base"
    elif "usdf-rsp" in location:
        site = "usdf"
    # If location not set, next step is to check hostname
    elif location == "":
        hostname = os.getenv("HOSTNAME", "")
        interactiveNodes = ("sdfrome", "sdfiana")
        if hostname.startswith(interactiveNodes):
            site = "usdf"
        elif hostname == "htcondor.ls.lsst.org":
            site = "base"
        elif hostname == "htcondor.cp.lsst.org":
            site = "summit"

    match site:
        case "summit":
            api_base = "https://summit-lsp.lsst.codes/"
            efd_client = EfdClient("summit_efd")
            obsenv_client = EfdClient("summit_efd", db_name="lsst.obsenv")
        case "tucson":
            api_base = None
            efd_client = EfdClient("tucson_teststand_efd")
            obsenv_client = EfdClient("tucson_teststand_efd", db_name="lsst.obsenv")
        case "base":
            api_base = "https://base-lsp.slac.lsst.codes/"
            efd_client = EfdClient("base_efd")
            obsenv_client = EfdClient("base_efd", db_name="lsst.obsenv")
        case _:
            if site != "usdf":
                warn(f"Unknown site {site}, defaulting to usdf.")
                site = "usdf"

            efd_client = EfdClient("usdf_efd")
            obsenv_client = EfdClient("usdf_efd", db_name="lsst.obsenv")
            api_base = "https://usdf-rsp.slac.stanford.edu/"

    return ClientConnections(api_base, efd_client, obsenv_client, auth)


def _get_efd_client(efd: EfdClient | str | None) -> EfdClient:
    match efd:
        case EfdClient():
            efd_client = efd
        case str():
            efd_client = EfdClient(efd)
        case None:
            efd_client = get_clients().efd
        case _:
            raise ValueError(f"Cannot translate a {type(efd)} to an EfdClient.")

    return efd_client


async def _get_efd_fields_for_topic(efd_client, topic, public_only=True):
    fields = await efd_client.get_fields(topic)
    if public_only:
        fields = [f for f in fields if "private" not in f]

    return fields


async def query_efd_topic_for_night(
    topic: str,
    day_obs: DayObs | str | int,
    sal_indexes: tuple[int, ...] = (1, 2, 3),
    efd: EfdClient | str | None = None,
    fields: list[str] | None = None,
) -> pd.DataFrame:
    """Query and EFD topic for all entries on a night.

    Parameters
    ----------
    topic : `str`
        The topic to query
    day_obs : `DayObs` or `str` or `int`
        The date of the start of the night requested.
    sal_indexes : `tuple[int, ...]`, optional
        Which SAL indexes to query, by default (1, 2, 3).
        Can be guessed by instrument with ``SAL_INDEX_GUESSES[instrument]``
    efd : `EfdClient` or `str`  `None`, optional
        The EFD client to use, by default None, which creates a new one
        based on the environment.
    fields : `list[str]` or `None`, optional
        Fields to query from the topic, by default None, which queries all
        fields.

    Returns
    -------
    result : `pd.DataFrame`
        The result of the query
    """

    day_obs = day_obs if isinstance(day_obs, DayObs) else DayObs.from_date(day_obs)
    efd_client = _get_efd_client(efd)

    if fields is None:
        fields = await _get_efd_fields_for_topic(efd_client, topic)

    if not isinstance(sal_indexes, Iterable):
        sal_indexes = [sal_indexes]

    results = []
    for sal_index in sal_indexes:
        result = await efd_client.select_time_series(
            topic, fields, day_obs.start, day_obs.end, index=sal_index
        )
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            results.append(result)

    result = pd.concat(results) if len(results) > 0 else pd.DataFrame()
    result.index.name = "time"

    return result


async def query_latest_in_efd_topic(
    topic: str,
    num_records: int = 6,
    sal_indexes: tuple[int, ...] = (1, 2, 3),
    efd: EfdClient | str | None = None,
    fields: list[str] | None = None,
) -> pd.DataFrame:
    """Query and EFD topic for all entries on a night.

    Parameters
    ----------
    topic : `str`
        The topic to query
    num_records : `int`
        The number of records to return.
    sal_indexes : `tuple[int, ...]`, optional
        Which SAL indexes to query, by default (1, 2, 3).
        Can be guessed by instrument with ``SAL_INDEX_GUESSES[instrument]``
    efd : `EfdClient` or `str`  `None`, optional
        The EFD client to use, by default None, which creates a new one
        based on the environment.
    fields : `list[str]` or `None`, optional
        Fields to query from the topic, by default None, which queries all
        fields.

    Returns
    -------
    result : `pd.DataFrame`
        The result of the query
    """

    efd_client = _get_efd_client(efd)

    if fields is None:
        fields = await _get_efd_fields_for_topic(efd_client, topic)

    if not isinstance(sal_indexes, Iterable):
        sal_indexes = [sal_indexes]

    results = []
    for sal_index in sal_indexes:
        result = await efd_client.select_top_n(topic, fields, num_records, index=sal_index)
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            results.append(result)

    result = pd.concat(results) if len(results) > 0 else pd.DataFrame()

    return result


def sync_query_efd_topic_for_night(*args, **kwargs):
    """Just like query_efd_topic_for_night, but run in a separate thread
    and block for results, so it can be run within a separate event loop.
    """
    # Inspired by https://stackoverflow.com/questions/74703727
    # Works even in a panel event loop
    io_loop = asyncio.new_event_loop()
    io_thread = threading.Thread(target=io_loop.run_forever, name="EFD query thread", daemon=True)

    def run_async(coro):
        if not io_thread.is_alive():
            io_thread.start()
        future = asyncio.run_coroutine_threadsafe(coro, io_loop)
        return future.result()

    result = run_async(query_efd_topic_for_night(*args, **kwargs))
    return result
