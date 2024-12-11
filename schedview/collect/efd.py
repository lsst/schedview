import os
from collections import defaultdict
from collections.abc import Iterable
from functools import partial

import pandas as pd
from lsst.summit.utils.efdUtils import makeEfdClient
from lsst_efd_client import EfdClient

from schedview.dayobs import DayObs

DEFAULT_EFD = (
    "summit_efd" if os.getenv("EXTERNAL_INSTANCE_URL", "") == "https://summit-lsp.lsst.codes" else "usdf_efd"
)
SAL_INDEX_GUESSES = defaultdict(partial([[]].__getitem__, 0), {"lsstcomcam": [1, 3], "latiss": [2]})


def _get_efd_client(efd: EfdClient | str | None) -> EfdClient:
    match efd:
        case EfdClient():
            efd_client = efd
        case str():
            efd_client = EfdClient(efd)
        case None:
            efd_client = makeEfdClient()
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
