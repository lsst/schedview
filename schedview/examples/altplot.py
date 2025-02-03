import argparse
import datetime

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import pandas as pd

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_alt_vs_time_plot(
    iso_date: str | datetime.date,
    visit_source: str,
    report: None | str = None,
) -> bokeh.models.UIElement:
    """Create an alt vs. time plot for a given night.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result : `bokeh.models.UIElement`
        The bokeh plot object with the map(s) of visits.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = schedview.collect.visits.read_visits(day_obs, visit_source)

    # Compute
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)

    # Plot
    result: bokeh.models.UIElement = schedview.plot.nightly.plot_alt_vs_time(
        visits=visits, almanac_events=night_events
    )

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="altplot", description="Write an html file a plot of alt vs. time.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_alt_vs_time_plot(args.date, args.visit_source, report=args.report)
