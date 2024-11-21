import argparse

import astropy.utils.iers
import pandas as pd
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview.compute.astro
from schedview import DayObs


def make_sun_moon_positions(night: str = "2025-11-11") -> pd.DataFrame:
    day_obs: DayObs = DayObs.from_date(night)

    # Get the time for which to get positions: the middle of the night
    # of the provided DayObs.
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)
    mjd = night_events.loc["night_middle", "MJD"]

    observatory: ModelObservatory = ModelObservatory(init_load_length=1, mjd=mjd)
    positions: pd.DataFrame = schedview.compute.astro.compute_sun_moon_positions(observatory)
    return positions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="sunmoon", description="Write an html file sun and moon coords.")
    parser.add_argument("night", type=str, help="Evening YYYY-MM-DD")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    positions = make_sun_moon_positions(args.night)

    print(positions)
