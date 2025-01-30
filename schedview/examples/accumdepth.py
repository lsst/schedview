import argparse
from typing import Literal

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import numpy as np
import pandas as pd
from bokeh.models.ui.ui_element import UIElement
from matplotlib.figure import Figure
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_sim import maf

import schedview.compute.visits
import schedview.plot
import schedview.plot.survey
from schedview.collect.visits import NIGHT_STACKERS, read_visits
from schedview.dayobs import DayObs


def make_accum_depth(
    iso_date: str,
    visit_source: str,
    report: None | str = None,
    backend: Literal["bokeh", "matplotlib"] = "matplotlib",
) -> Figure | UIElement | None:
    """Make an accumulated depth map

    Parameters
    ----------
    iso_date : `str`
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
    stackers = NIGHT_STACKERS + [maf.stackers.TeffStacker()]
    visits: pd.DataFrame = read_visits(day_obs, visit_source, stackers=stackers)
    previous_visits: pd.DataFrame = read_visits(
        DayObs.from_date(day_obs.mjd - 1, int_format="mjd"), visit_source, stackers=stackers, num_nights=10000
    )

    # Compute
    observatory: ModelObservatory = ModelObservatory(no_sky=True, mjd=day_obs.mjd)

    # Plot
    teff_key = "eff_time_median" if "eff_time_median" in visits.columns else "t_eff"
    result: Figure | UIElement | None = schedview.plot.survey.create_metric_visit_map_grid(
        maf.SumMetric(col=teff_key, metric_name="Total effective exposure time"),
        previous_visits.loc[np.isfinite(previous_visits[teff_key]), :],
        visits.loc[np.isfinite(visits[teff_key]), :],
        observatory,
        nside=32,
        use_matplotlib=use_matplotlib,
    )

    # Report
    if report is not None:
        if isinstance(result, UIElement):
            with open(report, "w") as report_io:
                print(bokeh.embed.file_html(result), file=report_io)
        elif isinstance(result, Figure):
            result.savefig(report)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="FIXME", description="FIXME")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_accum_depth(args.date, args.visit_source, args.report)
