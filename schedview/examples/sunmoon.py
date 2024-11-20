import pandas as pd
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview.compute.astro
from schedview import DayObs


def sun_moon_positions(day_obs: DayObs = DayObs.from_date("2025-11-11")) -> pd.DataFrame:
    # Get the time for which to get positions: the middle of the night
    # of the provided DayObs.
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)
    mjd = night_events.loc["night_middle", "MJD"]

    observatory: ModelObservatory = ModelObservatory(init_load_length=1, mjd=mjd)
    positions: pd.DataFrame = schedview.compute.astro.compute_sun_moon_positions(observatory)
    return positions
