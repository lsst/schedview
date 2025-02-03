import argparse
import datetime

import astropy.utils.iers
import pandas as pd

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_gaps(
    iso_date: str | datetime.date,
    visit_source: str,
    report: None | str = None,
) -> str:
    """Make a figure showing the gaps between visits.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result: `str`
        An html fragment with a definition list of the gaps between visits.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    # Compute
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)
    overhead_summary: dict = schedview.compute.visits.compute_overhead_summary(
        visits, night_events.loc["sun_n12_setting", "MJD"], night_events.loc["sun_n12_rising", "MJD"]
    )
    """A dictionary summarizing the overheads of the visits."""

    # Plot
    result: str = schedview.plot.create_overhead_summary_table(overhead_summary)
    """An HTML definition list summarizing the overheads of the visits."""

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(f"<html><body>{result}</body></html>", file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="gaps", description="Report on visit timing and gaps in a night.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_gaps(args.date, args.visit_source, args.report)
