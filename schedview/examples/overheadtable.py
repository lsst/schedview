import argparse

import astropy.utils.iers
import pandas as pd

import schedview.collect.visits
import schedview.compute.astro
import schedview.compute.visits
import schedview.plot
from schedview import DayObs


def make_overhead_table(
    night: str = "2026-11-11",
    visit_source: str = "3.5",
) -> str:

    day_obs: DayObs = DayObs.from_date(night)

    # Get the time for which to get positions: the middle of the night
    # of the provided DayObs.
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)

    # Get the visits
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    overhead_summary = schedview.compute.visits.compute_overhead_summary(
        visits,
        night_events.loc["sun_n12_setting", "MJD"],
        night_events.loc["sun_n12_rising", "MJD"],
    )
    summary_table = schedview.plot.create_overhead_summary_table(overhead_summary)
    return summary_table


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="overheadtable", description="Write an html file visit overhead data."
    )
    parser.add_argument("filename", type=str, help="output file name")
    parser.add_argument("night", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    overhead = make_overhead_table(args.night, args.visit_source)
    with open(args.filename, "w") as html_io:
        print("<html><body>", file=html_io)
        print(overhead, file=html_io)
        print("</body></html>", file=html_io)
