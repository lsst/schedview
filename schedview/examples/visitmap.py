import argparse

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models
import pandas as pd
import uranography.api
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_visit_map(
    iso_date: str,
    visit_source: str,
    nside: int = 8,
    map_classes=[uranography.api.ArmillarySphere, uranography.api.Planisphere],
    report: None | str = None,
) -> bokeh.models.UIElement:
    """_summary_

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    nside: `int`, optional
        The nside of the map to show, by default 8.
    map_classes: `list`, optional
        A list of uranography map classes to use, by default
        `[uranography.api.ArmillarySphere, uranography.api.Planisphere]`.
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
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )
    footprint = schedview.collect.footprint.get_footprint(nside)

    # Compute
    observatory: ModelObservatory = ModelObservatory(nside=nside, init_load_length=1)
    observatory.mjd = visits.observationStartMJD.max()
    conditions = observatory.return_conditions()
    visits: pd.DataFrame = schedview.compute.visits.add_coords_tuple(visits)

    # Plot
    result: bokeh.models.UIElement = schedview.plot.visitmap.plot_visit_skymaps(
        visits, footprint, conditions, map_classes=map_classes
    )

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="visitmap", description="Make interactive maps of visits.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("report", type=str, help="output file name")
    parser.add_argument("--nside", type=int, default=16, help="nside of map to show")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_visit_map(args.date, args.visit_source, args.nside, report=args.report)
