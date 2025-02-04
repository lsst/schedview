import asyncio
import threading
from collections import defaultdict
from collections.abc import Iterable
from functools import cache, partial
from typing import Literal

import pandas as pd
from lsst_efd_client import EfdClient

import schedview.clientsite
from schedview.dayobs import DayObs

EfdDatabase = Literal["efd", "lsst.obsenv"]

SAL_INDEX_GUESSES = defaultdict(partial([[]].__getitem__, 0), {"lsstcomcam": [1, 3], "latiss": [2]})


async def _get_efd_fields_for_topic(topic: str, public_only: bool = True, db_name: EfdDatabase = "efd"):
    client = EfdClient(schedview.clientsite.EFD_NAME, db_name=db_name)

    fields = await client.get_fields(topic)
    if public_only:
        fields = [f for f in fields if "private" not in f]

    return fields


async def query_efd_topic_for_night(
    topic: str,
    day_obs: DayObs | str | int,
    sal_indexes: tuple[int, ...] = (1, 2, 3),
    fields: list[str] | None = ["*"],
    db_name: EfdDatabase = "efd",
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
    fields : `list[str]` or `None`, optional
        Fields to query from the topic, by default ['*'].
    db_name : `str`, optional
        Which EFD db_name to query: ``efd`` or ``obsenv``,
        by default ``efd``.

    Returns
    -------
    result : `pd.DataFrame`
        The result of the query
    """

    day_obs = day_obs if isinstance(day_obs, DayObs) else DayObs.from_date(day_obs)
    client = EfdClient(schedview.clientsite.EFD_NAME, db_name=db_name)

    if fields is None:
        fields = await _get_efd_fields_for_topic(topic, db_name=db_name)

    if not isinstance(sal_indexes, Iterable):
        sal_indexes = [sal_indexes]

    results = []
    for sal_index in sal_indexes:
        result = await client.select_time_series(topic, fields, day_obs.start, day_obs.end, index=sal_index)
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            results.append(result)

    result = pd.concat(results) if len(results) > 0 else pd.DataFrame()
    result.index.name = "time"

    return result


async def query_latest_in_efd_topic(
    topic: str,
    num_records: int = 6,
    sal_indexes: tuple[int, ...] | None = None,
    fields: list[str] | None = ["*"],
    db_name: EfdDatabase = "efd",
) -> pd.DataFrame:
    """Query and EFD topic for all entries on a night.

    Parameters
    ----------
    topic : `str`
        The topic to query
    num_records : `int`
        The number of records to return.
    sal_indexes : `tuple[int, ...]` or `None`, optional
        Which SAL indexes to query, by default None, which gets data
        for all indexes.
        Can be guessed by instrument with ``SAL_INDEX_GUESSES[instrument]``
    fields : `list[str]` or `None`, optional
        Fields to query from the topic, by default ['*'].
    db_name : `str`, optional
        Which EFD db_name to query: ``efd`` or ``obsenv``,
        by default ``efd``.

    Returns
    -------
    result : `pd.DataFrame`
        The result of the query
    """
    client = EfdClient(schedview.clientsite.EFD_NAME, db_name=db_name)

    if fields is None:
        fields = await _get_efd_fields_for_topic(topic, db_name=db_name)

    if sal_indexes is None:
        result = await client.select_top_n(topic, fields, num_records)
        assert isinstance(result, pd.DataFrame)
    else:
        if not isinstance(sal_indexes, Iterable):
            sal_indexes = [sal_indexes]

        results = []
        assert isinstance(sal_indexes, Iterable)
        for sal_index in sal_indexes:
            result = await client.select_top_n(topic, fields, num_records, index=sal_index)
            if isinstance(result, pd.DataFrame) and len(result) > 0:
                results.append(result)

        result = pd.concat(results) if len(results) > 0 else pd.DataFrame()

    return result


@cache
def _loop_thread_for_efd_query() -> tuple[asyncio.AbstractEventLoop, threading.Thread]:
    # Make an event loop in a threead to run async calls.
    # The use of this function is paired with _run_async, below.
    # See https://stackoverflow.com/questions/74703727
    # Use the cache decorator to avoid creating a new loop & thread each time,
    # and instead just use the same ones each time.
    io_loop = asyncio.new_event_loop()
    io_thread = threading.Thread(target=io_loop.run_forever, name="EFD query thread", daemon=True)
    return (io_loop, io_thread)


def _run_async(coro):
    # Run the async call in its own thread to keep it from getting tangled
    # up in the panel event loop, if there is one.
    # Inspired by https://stackoverflow.com/questions/74703727
    io_loop, io_thread = _loop_thread_for_efd_query()
    if not io_thread.is_alive():
        io_thread.start()
    future = asyncio.run_coroutine_threadsafe(coro, io_loop)
    return future.result()


def sync_query_efd_topic_for_night(*args, **kwargs):
    """Just like query_efd_topic_for_night, but run in a separate thread
    and block for results, so it can be run within a separate event loop.
    """
    result = _run_async(query_efd_topic_for_night(*args, **kwargs))
    return result
