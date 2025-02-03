import argparse
import datetime
from typing import Literal

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import colorcet
import pandas as pd
from bokeh.models.ui.ui_element import UIElement
from matplotlib.figure import Figure
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_sim import maf

import schedview.compute.visits
import schedview.plot
import schedview.plot.survey
from schedview.collect.visits import read_visits
from schedview.dayobs import DayObs


def make_agemap(
    iso_date: str | datetime.date,
    visit_source: str,
    report: None | str = None,
    backend: Literal["bokeh", "matplotlib"] = "matplotlib",
) -> Figure | UIElement | None:
    """Make an a map of time since most recent visit.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).
    backend : `str`, optional
        The plotting backend to use: ``bokeh`` or ``matplotlib``, defaults
        to ``matplotlib``.

    Returns
    -------
    result: `Figure` or `UIElement` or None
        The plot, if there is one.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)
    use_matplotlib: bool = backend == "matplotlib"

    # Collect
    visits: pd.DataFrame = read_visits(day_obs, visit_source)
    previous_visits: pd.DataFrame = read_visits(
        DayObs.from_date(day_obs.mjd - 1, int_format="mjd"), visit_source, num_nights=10000
    )

    # Compute
    observatory: ModelObservatory = ModelObservatory(no_sky=True, mjd=day_obs.mjd)
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)

    # Plot
    result: Figure | UIElement | None = schedview.plot.survey.create_metric_visit_map_grid(
        maf.AgeMetric(night_events.loc["sunset", "MJD"]),
        previous_visits,
        visits,
        observatory,
        nside=32,
        use_matplotlib=use_matplotlib,
        vmin=0,
        vmax=10,
        cmap=colorcet.cm.blues_r,
    )

    # Report
    if report is not None:
        match result:
            case UIElement():
                with open(report, "w") as report_io:
                    print(bokeh.embed.file_html(result), file=report_io)
            case Figure():
                result.savefig(report)
            case _:
                assert False, "Unrecoginzed backend {backend}"

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="agemap", description="Plot the age of the most recent visit.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_agemap(args.date, args.visit_source, args.report)
