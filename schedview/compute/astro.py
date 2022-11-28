import numpy as np
import pandas as pd
from astropy.time import Time
from rubin_sim.site_models.almanac import Almanac
from rubin_sim.scheduler.modelObservatory import Model_observatory
import holoviews as hv

def night_events(night_date=None, site=None, timezone="Chile/Continental"):
    """Creata a pandas.DataFrame with astronomical events.

    Parameters
    ----------
    night_date : `str`, `astropy.time.Time`
        The night for which to get events. Defaults to now.
    site : `astropy.coordinates.earth.EarthLocation`
        The observatory location. Defaults to Rubin observatory.
    timezone: `str`
        The timezone name. Defaults to 'Chile/Continental'
        
    Returns
    -------
    events : `holoviews.Dataset`
        A Dataset of night events.
    """
    if night_date is None:
        night_date = Time.now()
        
    if site is None:
        site = Model_observatory().location

    night_mjd = Time(night_date).mjd
    all_nights_events = pd.DataFrame(Almanac().sunsets).set_index('night')
    first_night = all_nights_events.index.min()
    night = first_night + np.floor(night_mjd) - np.floor(all_nights_events.loc[first_night, 'sunset'])
    mjds = all_nights_events.loc[night]

    ap_times = Time(mjds, format="mjd", scale="utc", location=site)
    time_df = pd.DataFrame(
        {
            "MJD": ap_times.mjd,
            "LST": ap_times.sidereal_time("apparent").deg,
            "UTC": pd.to_datetime(ap_times.iso).tz_localize("UTC"),
        },
        index=mjds.index,
    )
    time_df[timezone] = time_df["UTC"].dt.tz_convert(timezone)
    time_df.index.name = 'event'
    
    return time_df