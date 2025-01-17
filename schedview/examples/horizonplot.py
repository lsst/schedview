import argparse

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import pandas as pd

import schedview.collect.visits
import schedview.plot
import schedview.plot.nightly
from schedview.dayobs import DayObs


def make_horizon_plot(
    iso_date: str,
    visit_source: str,
    report: None | str = None,
) -> bokeh.models.UIElement:
    """Create an horzon (alt/az) plot for a given night.

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
    result : `bokeh.models.UIElement`
        The bokeh plot object with the map(s) of visits.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs,
        visit_source,  # stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    # Plot
    result: bokeh.models.UIElement = schedview.plot.nightly.plot_polar_alt_az(visits=visits)

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="horizonplot", description="Write an html file a plot of alt and az."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_horizon_plot(args.date, args.visit_source, report=args.report)
