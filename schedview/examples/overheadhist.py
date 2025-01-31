import argparse

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import pandas as pd

import schedview.compute.visits
import schedview.plot
from schedview.collect.visits import NIGHT_STACKERS, read_visits
from schedview.dayobs import DayObs


def make_overhead_hist(
    iso_date: str,
    visit_source: str,
    report: None | str = None,
) -> bokeh.models.UIElement:
    """Make a histogram of overhead between visits.

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result: `bokeh.models.UIElement`
        The histogram.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = read_visits(day_obs, visit_source, stackers=NIGHT_STACKERS)

    # Compute

    # Plot
    result: bokeh.models.UIElement = schedview.plot.create_overhead_histogram(visits)

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="overheadhist", description="Make a histogram of overhead between visits."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_overhead_hist(args.date, args.visit_source, args.report)
