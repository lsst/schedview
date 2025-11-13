import asyncio
import re
import threading
from collections import defaultdict
from collections.abc import Iterable
from functools import cache, partial
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import requests
from astropy.time import Time, TimeDelta
from lsst_efd_client import EfdClient

import schedview.clientsite
from schedview.dayobs import DayObs

EfdDatabase = Literal["efd", "lsst.obsenv"]
ScheduledThing = Literal["simonyi", "lsstcam", "maintel", "latiss", "auxtel"]

SAL_INDEX_GUESSES = defaultdict(
    partial([[]].__getitem__, 0),
    {
        "lsstcam": [1, 3],
        "lsstcomcam": [1, 3],
        "latiss": [2],
        "auxtel": [2],
        "maintel": [1],
        "simonyi": [1],
        "ocs": [3],
    },
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


def get_scheduler_config(what_scheduled, time_cut: Optional[Time] = None) -> tuple[str, str]:
    """Retrieve the Git reference and path for the scheduler configuration used
    at a given time.

    Parameters
    ----------
    what_scheduled : str
        Identifier of the scheduled component (e.g. ``"maintel"``,
        ``"auxtel"``, ``"simonyi"``, ``"latiss"``, ``"lsstcam"``).
    time_cut : astropy.time.Time, optional
        Timestamp at which to query the configuration.
        If ``None`` (default), the current time is used.

    Returns
    -------
    git_reference: str
        The Git reference (commit hash, tag, or branch name) that
        corresponds to the version recorded in the EFD for the requested
        component.
    config_path: str
        A relative path to the scheduler configuration file within the
        ``ts_config_scheduler`` repository.

    Raises
    ------
    ValueError
        If the recorded version cannot be matched to a Git reference, or if the
        configuration record is missing required fields.
    """
    if time_cut is None:
        time_cut = Time.now()
    assert isinstance(time_cut, Time)

    # Query the EFD for the version recorded
    raw_version, configurations, url = sync_query_latest_in_efd_topic(
        topic="lsst.sal.Scheduler.logevent_configurationApplied",
        num_records=1,
        db_name="efd",
        fields="version, configurations, url",
        time_cut=time_cut,
        sal_indexes=SAL_INDEX_GUESSES[what_scheduled.lower()],
    ).iloc[0]

    if not isinstance(raw_version, str):
        raise ValueError("Unexpected type for version of ts_config_scheduler in EFD")

    assert isinstance(raw_version, str)

    # Initialize git_reference to None to mean we haven't found a ref
    # for the returned version (yet).
    git_reference: str | None = None

    # The versions seem to usually be a git describe style string that looks
    # something like this: heads/temp-0-gb94a182
    # implying that it's a commit on a branch called "temp"
    # This branch isn't available on github, but it looks like commits
    # that match the implied hash (the 7 characters at the end of
    # the string, after the "g") are sometimes (but not always) there.

    # Begin by testing to see if it is of that form, and if it is, extract
    # the hash:
    match = re.search(r"^heads/.*-g([0-9a-fA-F]+)$", raw_version)
    if match is not None and len(match.group(1)) >= 6:
        commit_hash = match.group(1)

        # The hash sometimes seems to be available on github, and if it is,
        # we can use it as our git reference. So, check whether it exists:
        commit_url = f"https://api.github.com/repos/lsst-ts/ts_config_scheduler/commits/{commit_hash}"
        commit_exists = requests.get(commit_url).status_code == 200
        if commit_exists:
            git_reference = commit_hash

    if git_reference is None:
        # If the version is a git reference (raw hash, tag, or branch)
        # available on github, return it "as is":
        for ref_type in ("commits", "git/ref", "git/ref/tags", "git/ref/heads"):
            ref_url = f"https://api.github.com/repos/lsst-ts/ts_config_scheduler/{ref_type}/{raw_version}"
            ref_exists = requests.get(ref_url).status_code == 200
            if ref_exists:
                git_reference = raw_version
                break

    if git_reference is None:
        raise ValueError(f"Recorded ts_config_scheduler version {raw_version} not available on github")

    assert isinstance(git_reference, str)

    # Now construct the path to the configuration
    # file within the repository.
    config_file = configurations.split(",")[-1]
    config_path_parts = url.split("/") + [config_file]
    config_path = Path(*config_path_parts[config_path_parts.index("ts_config_scheduler") :]).as_posix()

    return git_reference, config_path
