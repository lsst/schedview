import argparse
import datetime

import astropy.utils.iers
import pandas as pd

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_night_events(
    iso_date: str | datetime.date,
    report: None | str = None,
) -> str:
    """Sample workflow to create a table of ephemeris events for a night.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result : `str`
        _description_
    """
    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect

    # Compute
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)

    # Plot
    result: str = night_events.to_string()

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="nightevents", description="Create a table of ephemeris events for a night."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_night_events(args.date, args.report)
