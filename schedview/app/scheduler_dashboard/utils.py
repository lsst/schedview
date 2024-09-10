import os
from datetime import datetime, timedelta, timezone

import astropy.units as u
import pandas as pd
from astropy.time import Time, TimeDelta
from lsst.resources import ResourcePath
from lsst_efd_client import EfdClient
from rubin_scheduler.skybrightness_pre.sky_model_pre import SkyModelPre

LOCAL_ROOT_URI = {"usdf": "s3://rubin:", "summit": "https://s3.cp.lsst.org/"}


async def query_night_schedulers(reference_time_utc, selected_telescope=None, efd=None):
    """Query the EFD for the night schedulers till reference time

    Parameters
    ----------
    reference_time_utc : `astropy.time.Time`
        selected reference time in UTC
    efd : `str` or `None`
        The name of the EFD to query, usdf_efd or summit_efd
        If None, it derives it from the LSST_SITE environment variable,
        and if that is not set, uses usdf_efd.

    Returns
    -------
    schedulers : `list`
        A list of the schedulers for the night
    """
    if efd is None:
        lfa_site = os.environ.get("LSST_SITE", "usdf")
        efd = f"{lfa_site}_efd"
    else:
        lfa_site = efd.split("_")[0]

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
        scheduler_urls["url"] = scheduler_urls["url"].apply(lambda x: localize_scheduler_url(x, lfa_site))
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


def get_sky_brightness_date_bounds():
    """Load available datetime range from SkyBrightness_Pre files.

    Returns
    -------
    (min_date, max_date): tuple[astropy.time.Time, astropy.time.Time]
    """
    sky_model = SkyModelPre()
    min_date = Time(sky_model.mjd_left.min(), format="mjd")
    max_date = Time(sky_model.mjd_right.max() - 0.001, format="mjd")
    return (min_date, max_date)


# Suggestion: Move to a utils module
def url_formatter(dataframe_row, name_column, url_column):
    """Format survey name as a HTML href to survey URL (if URL exists).

    Parameters
    ----------
    dataframe_row : 'pandas.core.series.Series'
        A row of a pandas.core.frame.DataFrame.

    Returns
    -------
    survey_name_or_url : 'str'
        A HTML href or plain string.
    """
    if dataframe_row[url_column] == "":
        return dataframe_row[name_column]
    else:
        return f'<a href="{dataframe_row[url_column]}" target="_blank"> \
            <i class="fa fa-link"></i></a>'
