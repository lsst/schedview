from datetime import datetime, timedelta, timezone

import astropy.units as u
import pandas as pd
from astropy.time import Time, TimeDelta
from lsst.resources import ResourcePath
from lsst_efd_client import EfdClient

LOCAL_ROOT_URI = {"usdf": "s3://rubin:", "summit": "https://s3.cp.lsst.org/"}


async def query_night_schedulers(reference_time_utc, selected_telescope=None, efd="usdf_efd"):
    """Query the EFD for the night schedulers till reference time

    Parameters
    ----------
    reference_time_utc : `astropy.time.Time`
        selected reference time in UTC
    efd : `str`
        The name of the EFD to query, usdf_efd or summit_efd
        Defaults to usdf_efd

    Returns
    -------
    schedulers : `list`
        A list of the schedulers for the night
    """
    # Use DOYOBS rollover as defined in SITCOMTN-32
    dayobs_tz = timezone(timedelta(hours=+12), "dayobs")
    reference_datetime_dayobs_tz = reference_time_utc.datetime.astimezone(dayobs_tz)
    start_datetime_utc = datetime(
        reference_datetime_dayobs_tz.year,
        reference_datetime_dayobs_tz.month,
        reference_datetime_dayobs_tz.day,
        tzinfo=dayobs_tz,
    ).astimezone(timezone(timedelta(hours=0), "UTC"))
    start_time = Time(start_datetime_utc)
    end_time = reference_time_utc

    efd_client = EfdClient(efd)
    topic = "lsst.sal.Scheduler.logevent_largeFileObjectAvailable"
    fields = ["url"]
    scheduler_urls = await efd_client.select_time_series(
        topic, fields, start_time, end_time, index=selected_telescope
    )

    # If there are no entries this night, give the night before.
    if scheduler_urls.empty:
        start_time = start_time - TimeDelta(1 * u.day)
        scheduler_urls = await efd_client.select_time_series(
            topic, fields, start_time, end_time, index=selected_telescope
        )

    # If there are no entries this night either, give up.
    if not scheduler_urls.empty:
        # index data by time
        scheduler_urls.index.name = "time"
        scheduler_urls = scheduler_urls.reset_index()
        # reverse schedulers order to show most recent one first
        scheduler_urls = scheduler_urls.sort_index(ascending=False)
        scheduler_urls["url"] = scheduler_urls["url"].apply(lambda x: localize_scheduler_url(x))
        # return only URLs
        return scheduler_urls["url"]
    return []


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
    return df["url"]
