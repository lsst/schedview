import argparse
import datetime

import astropy.utils.iers
import pandas as pd

from schedview.collect.visits import NIGHT_STACKERS, read_visits
from schedview.dayobs import DayObs


def make_overhead_table(
    iso_date: str | datetime.date, visit_source: str, report: None | str = None, min_time: float = 30
) -> str:
    """Create a table of overheads between visits.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).
    min_time : `float`, optional
        The minimim duration of gaps to show (seconds). Defaults to 30.

    Returns
    -------
    result : `str`
        The table of long overheads.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = read_visits(day_obs, visit_source, stackers=NIGHT_STACKERS)

    # Compute
    for time_column in "obs_start", "observationStartDatetime64":
        if time_column in visits:
            break

    visits["previous_filter"] = visits["filter"].shift(1)
    long_gap_visits: pd.DataFrame = (
        visits.sort_values("overhead", ascending=False)
        .query(f"overhead>{min_time}")
        .loc[:, [time_column, "overhead", "slewDistance", "filter", "previous_filter"]]
        .sort_values(time_column)
    )

    # Plot
    result: str = long_gap_visits.to_markdown()

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="overheadtable", description="Create a table of long overheads between visits for a night."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    parser.add_argument("--dt", type=float, default=30.0, help="Minimum gap duration to show (seconds)")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_overhead_table(args.date, args.visit_source, args.report, args.dt)
