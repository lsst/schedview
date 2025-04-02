import asyncio
import threading
from collections import defaultdict
from collections.abc import Iterable
from functools import cache, partial
from typing import Literal

import pandas as pd
import requests
import yaml
from astropy.time import Time, TimeDelta
from lsst_efd_client import EfdClient

import schedview.clientsite
from schedview.dayobs import DayObs

EfdDatabase = Literal["efd", "lsst.obsenv"]

SAL_INDEX_GUESSES = defaultdict(
    partial([[]].__getitem__, 0), {"lsstcam": [1, 3], "lsstcomcam": [1, 3], "latiss": [2]}
)


def make_efd_client(efd_name: str | None = None, *args, **kwargs):
    """Factor to create and EFD client.

    Parameters
    ----------
    efd_name : `str` or `None`
        Name of the EFD instance for which to retrieve credentials.
        If None, use ``schedview.clientsite.EFD_NAME``.
        By default, None.
    *args
        As `lsst_efd_client.EfdClient`
    **kwargs
        As `lsst_efd_client.EfdClient`

    Returns
    -------
    client : `lsst_efd_client.EfdClient`
        An EfdClient
    """
    if efd_name is None:
        efd_name = schedview.clientsite.EFD_NAME

    assert isinstance(efd_name, str)
    return EfdClient(efd_name, *args, **kwargs)


async def _get_efd_fields_for_topic(topic: str, public_only: bool = True, db_name: EfdDatabase = "efd"):
    client = make_efd_client(db_name=db_name)

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
    client = make_efd_client(db_name=db_name)

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
    time_cut: Time | None = None,
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
    time_cut: `astropy.time.Time` or `None`, optional
        Use a time cut instead of the most recent entry.
        (default is `None`)

    Returns
    -------
    result : `pd.DataFrame`
        The result of the query
    """
    client = make_efd_client(db_name=db_name)

    # select_to_n only works when fromat=isot
    if time_cut is not None and time_cut.format != "isot":
        time_cut = Time(time_cut, format="isot")

    if fields is None:
        fields = await _get_efd_fields_for_topic(topic, db_name=db_name)

    if sal_indexes is None:
        result = await client.select_top_n(topic, fields, num_records, time_cut=time_cut)
        assert isinstance(result, pd.DataFrame)
    else:
        if not isinstance(sal_indexes, Iterable):
            sal_indexes = [sal_indexes]

        results = []
        assert isinstance(sal_indexes, Iterable)
        for sal_index in sal_indexes:
            result = await client.select_top_n(topic, fields, num_records, index=sal_index, time_cut=time_cut)
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


def sync_query_latest_in_efd_topic(*args, **kwargs):
    """Just like query_latest_in_efd_topic, but run in a separate thread
    and block for results, so it can be run within a separate event loop.
    """
    result = _run_async(query_latest_in_efd_topic(*args, **kwargs))
    return result


def make_version_table_for_time(time_cut=None):
    """Query for the versions used as of a given time.

    Parameters
    ----------
    time_cut : `Time` | `None`, optional
        The time at which you want the version.

    Returns
    -------
    versions : `pd.DataFrame`
        The table of versions as of the requested time.
    """
    # We will collect our versions for multiple queries, which will be
    # combined later.
    # Initialize a list of the results of the various queries:
    collected_versions = []

    # Start with obsenv
    topic: str = "lsst.obsenv.summary"
    db_name: str = "lsst.obsenv"
    collected_versions.append(
        sync_query_latest_in_efd_topic(topic, num_records=1, db_name=db_name, fields="*", time_cut=time_cut)
    )

    # Now scheduler items
    topic = "lsst.sal.Scheduler.logevent_dependenciesVersions"
    db_name = "efd"
    collected_versions.append(
        sync_query_latest_in_efd_topic(
            topic, num_records=1, db_name=db_name, fields="*", time_cut=time_cut
        ).rename(columns={"version": "rubin_scheduler"})
    )

    # Hack to guess rubin_scheduler version from available columns
    # if version is missing a value
    if collected_versions[-1]["rubin_scheduler"].iloc[0] == "":
        collected_versions[-1]["rubin_scheduler"] = collected_versions[-1]["seeingModel"]

    # Reshape returned values to have one row for each versioned item.
    version_tables = []
    for collected_df in collected_versions:
        config_time = collected_df.index[0]
        version_tables.append(collected_df.T)
        version_tables[-1].columns = ["version"]
        version_tables[-1]["time"] = config_time

    # Combine the versions from our various queries into a single DataFrame,
    result = pd.concat(version_tables)

    nonproduct_rows = [
        c
        for c in result.index
        if c.startswith("private_") or c in ["salIndex", "priority", "SchedulerID", "timestamp"]
    ]
    result.drop(nonproduct_rows, axis=0, inplace=True)

    return result


def get_version_at_time(item: str, time_cut: Time | None = None, max_age: TimeDelta | None = None) -> str:
    """Query for the version of something being used at a given time.

    Parameters
    ----------
    item : `str`
        The thing to get the version of.
    time_cut : `Time` | `None`, optional
        The time at which you want the version.
    max_age : `TimeDelta` | `None`, optional
        The most time between the requested cut and the time the version was
        recorded to consider it valid.

    Returns
    -------
    version : `str`
        The version of the requested item.
    """
    versions = make_version_table_for_time(time_cut)

    if max_age is not None:
        version_time = Time(versions.loc[item, "time"])
        age = (Time.now() - version_time) if time_cut is None else (time_cut - version_time)
        if age > max_age:
            raise ValueError(f"Most recent version record is too old, recorded at {version_time}")

    version = versions.loc[item, "version"]
    if not isinstance(version, str):
        raise ValueError(
            f"Invalid version name for {item} in consdb: expected a string, got a {type(version)}"
        )

    return version


async def get_scheduler_config(
    ts_config_ocs_version: str, sal_indexes: tuple[int, ...] | None = None, time_cut: Time | None = None
) -> str:
    """Get the relative path of the scheduler configuration script.

    Parameters
    ----------
    ts_config_ocs_version : `str`
        The version of ts_config_ocs from which to fetch the configuration.
        Must be a valid string representing the git branch or tag.
    sal_indexes : `tuple` of `int` or `None`
        Optional. SAL indexes to filter results by.
        Default is None (no filtering).
        Example: (1, 3)
    time_cut : `astropy.time.Time` or `None`
        The time cut for the query. Default is None, which
        uses the current time.

    Returns
    -------
    config_script_path : `str`
        The relative path to the scheduler configuration script.

    """

    latest_config_df = await query_latest_in_efd_topic(
        topic="lsst.sal.Scheduler.logevent_configurationApplied",
        fields=["SchedulerId", "configurations", "salIndex", "schemaVersion", "url", "version"],
        sal_indexes=sal_indexes,
        time_cut=time_cut,
        num_records=1,
    )

    # Find the name of the yaml configuration file for the FBS
    # This is typically saved in the last comma-separated values in the
    # "configurations" field from
    # lsst.sal.Scheduler.logevent_configurationApplied
    config_fname = latest_config_df["configurations"].iloc[0].split(",")[-1]

    # schema_version tracks the directory where the above yaml
    # configuration file should live inside of ts_config_ocs/Scheduler
    schema_version = latest_config_df["schemaVersion"].iloc[0]

    scheduler_config_ocs_url = "/".join(
        [
            "https://raw.githubusercontent.com",
            "lsst-ts",
            "ts_config_ocs",
            ts_config_ocs_version,
            "Scheduler",
            schema_version,
            config_fname,
        ]
    )

    response = requests.get(scheduler_config_ocs_url, allow_redirects=True)
    scheduler_config_ocs = yaml.safe_load(response.content.decode("utf-8"))

    # Find the path to actual python configuration file
    # for the FBS referenced in the yaml file
    scheduler_config = scheduler_config_ocs["auxtel"]["feature_scheduler_driver_configuration"][
        "scheduler_config"
    ]

    # Find the path to the FBS python configuration,
    # relative to ts_config_ocs/Scheduler/feature_scheduler
    # The "+1" skips the initial "/", resulting in a relative path,
    # while still only matching when ts_config_ocs is the full
    # name of the higest-level named directory.
    relative_scheduler_config = scheduler_config[
        scheduler_config.find("/ts_config_ocs/Scheduler/feature_scheduler") + 1 :
    ]
    return relative_scheduler_config
