import argparse
from contextlib import redirect_stdout

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.layouts
import bokeh.models
import pandas as pd

import schedview.compute.visits
import schedview.plot
from schedview.collect.visits import NIGHT_STACKERS, read_visits
from schedview.dayobs import DayObs


def make_overhead_figures(
    iso_date: str, visit_source: str, report: None | str = None, min_time: float = 30
) -> bokeh.models.UIElement:
    """Make a report including figures on overhead.

    Parameters
    ----------
    iso_date : `str`
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
    result: `dict`
        A dictionary of the figures related to overhead.
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
    histogram: bokeh.models.UIElement = schedview.plot.create_overhead_histogram(visits)
    vsslew: bokeh.models.UIElement = schedview.plot.plot_overhead_vs_slew_distance(visits)
    table: str = long_gap_visits.to_html()
    result = {
        "histogram": histogram,
        "vsslew": vsslew,
        "table": table,
    }

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            with redirect_stdout(report_io):
                print("<html><body>")
                print(f"<h1>Overhead between visits for {day_obs}</h1>")
                print("<h2>Plots</h2>")
                print(bokeh.embed.file_html(bokeh.layouts.row([histogram, vsslew])))
                print("<h2>Table</h2>")
                print(table)
                print("<html><body>")

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
    parser.add_argument("--dt", type=float, default=30.0, help="Minimum gap duration to show (seconds)")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_overhead_figures(args.date, args.visit_source, args.report, args.dt)
