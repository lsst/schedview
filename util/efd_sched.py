"""Developer utilities to query the EFD for schedulers, and download them.
"""

import argparse
import asyncio
import lzma
import os
import pickle
import re

import astropy.units as u
from astropy.time import Time, TimeDelta
from lsst.resources import ResourcePath
from lsst_efd_client import EfdClient
from rubin_sim.utils import Site


async def query_schedulers_in_window(desired_time, efd="usdf_efd", time_window=TimeDelta(2 * u.second)):
    """Query the EFD for scheduler URLs within a given time window.

    Parameters
    ----------
    desired_time : `astropy.time.Time`
        The central time to query the event service.
    efd : `str`, optional
        The name of the EFD to connect to (default is 'usdf_efd').
    time_window : `astropy.time.TimeDelta`, optional
        The size of the time window to search for scheduler URLs
        (default is 2 seconds).

    Returns
    -------
    scheduler_urls : `pandas.DataFrame`
        A DataFrame containing the scheduler snapshot times URLs.
    """
    start_time = desired_time - (time_window / 2)
    end_time = desired_time + (time_window / 2)

    efd_client = EfdClient(efd)
    topic = "lsst.sal.Scheduler.logevent_largeFileObjectAvailable"
    fields = ["url"]
    scheduler_urls = await efd_client.select_time_series(topic, fields, start_time, end_time)
    scheduler_urls.index.name = "time"
    scheduler_urls = scheduler_urls.reset_index()
    return scheduler_urls


async def query_night_schedulers(night, efd="usdf_efd"):
    """Query the EFD for the night schedulers

    Parameters
    ----------
    night : `str`, 'float', or `astropy.time.Time`
        The night to query, in YYYY-MM-DD format
    efd : `str`
        The name of the EFD to query, usdf_efd or summit_efd
        Defaults to usdf_efd

    Returns
    -------
    schedulers : `list`
        A list of the schedulers for the night
    """

    try:
        reference_time = Time(night)
    except ValueError:
        if isinstance(night, int):
            reference_time = Time(night, format="mjd")
        else:
            raise ValueError("night must be a valid date in YYYY-MM-DD format")

    # The offset by longitude moves to local solar time.
    # The offset of 1 makes the night specificed refer to the
    # local date corresponding to sunset.
    local_midnight = Time(reference_time.mjd + 1 - Site("LSST").longitude / 360, format="mjd")
    time_window = TimeDelta(1, format="jd")
    scheduler_urls = await query_schedulers_in_window(local_midnight, efd=efd, time_window=time_window)
    return scheduler_urls


def get_scheduler(scheduler_url, destination=None):
    """Load a scheduler, conditions tuple from a URI and optionally save it.

    Parameters
    ----------
    scheduler_url : `str`
        The URL of the scheduler to load.
    destination : `str`, optional
        The file path to save the scheduler to.
        If None, the (scheduler, conditions) tuple will be returned.

    Returns
    -------
    result : `tuple` or `str`
        If `destination` is None, the loaded scheduler (scheduler, conditions)
        tuple is returned.
        Otherwise, the file path of the saved scheduler is returned.

    Notes
    -----
    This function sets the environment variable
    `LSST_DISABLE_BUCKET_VALIDATION` to "1".
    """

    os.environ["LSST_DISABLE_BUCKET_VALIDATION"] = "1"
    scheduler_resource_path = ResourcePath(scheduler_url.replace("https://s3.cp.lsst.org/", "s3://rubin:"))
    scheduler_pickle_bytes = scheduler_resource_path.read()

    if destination is None:
        result = pickle.loads(scheduler_pickle_bytes)
    else:
        if os.path.isdir(destination):
            base_file_name = (
                scheduler_resource_path.basename()
                .replace("Scheduler:2_Scheduler:2", "auxtel")
                .replace(":", "")
                + ".xz"
            )
            file_name = os.path.join(destination, base_file_name)
        else:
            file_name = destination

        this_open = lzma.open if file_name.endswith(".xz") else open
        with this_open(file_name, "wb") as this_file:
            this_file.write(scheduler_pickle_bytes)

        result = file_name

    return result


async def get_scheduler_at_time(desired_time, destination=None, efd="usdf_efd"):
    """Get the scheduler, conditions tuple for a desired time.

    Parameters
    ----------
    desired_time : `str`
        The desired time to get the scheduler for in iso8601 format.
    destination : `str`, optional
        The file path to save the scheduler to.
        If None, the (scheduler, conditions) tuple is returned.
    efd : `str`, optional
        The EFD to query for schedulers. Defaults to 'usdf_efd'.

    Returns
    -------
    result : `tuple` or `str`
        If `destination` is None, the loaded (scheduler, conditions) tuple
        is returned.
        Otherwise, the file path of the saved scheduler is returned.
    """
    these_scheduler_references = await query_schedulers_in_window(desired_time, efd)
    this_url = these_scheduler_references.url[0]
    result = get_scheduler(this_url, destination)
    return result


async def get_scheduler_on_night(night, scheduler_index, destination, efd="usdf_efd"):
    """Get a scheduler for a given night from the EFD.

    Parameters
    ----------
    night : `str`
        The night for which to get the scheduler.
    scheduler_index : `int`, optional
        The index of the scheduler to retrieve (default is 0).
    destination : `str`, optional
        The file path to save the scheduler to.
        If None, the (scheduler, conditions) tuple is returned.
    efd : `str`, optional
        The EFD to query (default is 'usdf_efd').

    Returns
    -------
    result : `np.ndarray`
        The scheduler for the given night.
    """
    these_scheduler_references = await query_night_schedulers(night, efd=efd)
    this_url = these_scheduler_references.url[scheduler_index]
    result = get_scheduler(this_url, destination)
    return result


async def main():
    parser = argparse.ArgumentParser(description="Query the EFD for a scheduler.")
    parser.add_argument(
        "datetime", help="The desired time or night to get the scheduler for in iso8601 format."
    )
    parser.add_argument(
        "--destination", type=str, default=None, help="The file path to save the scheduler to."
    )
    parser.add_argument(
        "--id", type=int, default=0, help="The index of the scheduler to retrieve (default is 0)."
    )
    parser.add_argument("--efd", default="usdf_efd", help="The EFD to query (default is 'usdf_efd').")
    args = parser.parse_args()

    mjd_date_regex = r"^\d{5}$"
    date_only_regex = r"^\d{4}-\d{2}-\d{2}$"
    if re.match(mjd_date_regex, args.datetime):
        night = Time(args.datetime, format="mjd")
        time_specified = False
    elif re.match(date_only_regex, args.datetime):
        night = Time(args.datetime)
        time_specified = False
    else:
        desired_time = Time(args.datetime)
        time_specified = True

    if args.destination is not None:
        if time_specified:
            file_name = await get_scheduler_at_time(desired_time, args.destination, args.efd)
        else:
            file_name = await get_scheduler_on_night(night, args.id, args.destination, args.efd)
        print(file_name)
    else:
        if time_specified:
            matching_schedulers = await query_schedulers_in_window(desired_time, args.efd)
        else:
            matching_schedulers = await query_night_schedulers(night, args.efd)

        print(matching_schedulers.to_csv(sep="\t"))


if __name__ == "__main__":
    asyncio.run(main())
