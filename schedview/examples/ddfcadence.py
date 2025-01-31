import argparse

import bokeh.embed
import bokeh.io
import bokeh.models
import pandas as pd

import schedview.compute.visits
import schedview.plot
from schedview.collect.visits import read_ddf_visits
from schedview.dayobs import DayObs


def make_ddf_cadence_plot(
    iso_date: str,
    visit_source: str,
    report: None | str = None,
    nights: int = 90,
) -> bokeh.models.UIElement:
    """_summary_

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).
    nights : `int`, optional
        Number of nights to cover, be default 90.

    Returns
    -------
    result : `bokeh.models.UIElement`
        The DDF cadence plot.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = read_ddf_visits(day_obs, visit_source, num_nights=nights)

    # Compute
    nightly_ddf = schedview.compute.visits.accum_teff_by_night(visits)

    # Plot
    result: bokeh.models.UIElement = schedview.plot.create_cadence_plot(
        nightly_ddf, day_obs.mjd - nights, day_obs.mjd
    )

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="ddfcadence", description="Make a DDF candence plot")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    parser.add_argument("--nights", type=int, default=90, help="output file name")
    args = parser.parse_args()

    make_ddf_cadence_plot(args.date, args.visit_source, args.report, nights=args.nights)
