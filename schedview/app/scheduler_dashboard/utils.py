import astropy.units as u
import pandas as pd
from astropy.time import Time, TimeDelta
from lsst.resources import ResourcePath
from lsst_efd_client import EfdClient
from rubin_scheduler.utils import Site

LOCAL_ROOT_URI = {"usdf": "s3://rubin:", "summit": "https://s3.cp.lsst.org/"}


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


def localize_scheduler_url(scheduler_url, site="usdf"):
    """Localizes the scheduler URL for a given site.

    Parameters
    ----------
    scheduler_url : `str`
        The URL of the scheduler to be localized.
    site : `str` , optional
        The site to which the scheduler URL should be localized.
        Defaults to 'usdf'.

    Returns
    -------
    scheduler_url : `str`
        The localized URL of the scheduler.
    """
    # If we don't have a canonical root for the site, just return
    # the original
    if site not in LOCAL_ROOT_URI:
        return scheduler_url

    original_scheduler_resource_path = ResourcePath(scheduler_url)
    scheduler_path = original_scheduler_resource_path.path.lstrip("/")
    root_uri = LOCAL_ROOT_URI[site]
    scheduler_url = f"{root_uri}{scheduler_path}"
    return scheduler_url


def mock_schedulers_df():
    data = [
        [
            "2024-03-12 00:30:40.565731+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:1/Scheduler:1/2024/03/11/Scheduler:1_Scheduler:1_2024-03-12T00:31:16.956.p",
        ],
        [
            "2024-03-12 00:32:29.309646+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T00:33:05.127.p",
        ],
        [
            "2024-03-12 00:57:23.035425+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T00:57:58.876.p",
        ],
        [
            "2024-03-12 01:06:34.583256+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T01:07:10.474.p",
        ],
        [
            "2024-03-12 01:15:09.624082+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T01:15:45.472.p",
        ],
        [
            "2024-03-12 01:22:38.678879+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T01:23:14.427.p",
        ],
        [
            "2024-03-12 01:34:39.499348+00:00",
            "https://s3.cp.lsst.org/rubinobs-lfa-cp/Scheduler:2/Scheduler:2/2024/03/11/Scheduler:2_Scheduler:2_2024-03-12T01:35:15.393.p",
        ],
    ]

    df = pd.DataFrame(data, columns=["time", "url"])
    df = df.sort_index(ascending=False)
    df["url"] = df["url"].apply(lambda x: localize_scheduler_url(x))
    return df
