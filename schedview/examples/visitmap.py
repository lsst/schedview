import argparse

import astropy.utils.iers
import bokeh.io
import pandas as pd
import uranography.api
from bokeh.models.ui.ui_element import UIElement
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_visit_map(
    night: str = "2026-03-15",
    visit_source: str = "3.5",
    nside: int = 8,
    map_classes=[uranography.api.ArmillarySphere],
) -> UIElement:

    day_obs: DayObs = DayObs.from_date(night)

    # Collect the data to be shown
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    footprint = schedview.collect.footprint.get_footprint(nside)
    observatory: ModelObservatory = ModelObservatory(nside=nside, init_load_length=1)
    observatory.mjd = visits.observationStartMJD.max()
    conditions = observatory.return_conditions()

    # Do computations required by mapping code
    visits: pd.DataFrame = schedview.compute.visits.add_coords_tuple(visits)

    # Make the map
    sky_map: UIElement = schedview.plot.visitmap.plot_visit_skymaps(
        visits, footprint, conditions, map_classes=map_classes
    )
    return sky_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="visittable", description="Write an html file with map of visits.")
    parser.add_argument("filename", type=str, help="output file name")
    parser.add_argument("night", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("--nside", type=int, default=32, help="nside of map to show")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    figure = make_visit_map(args.night, args.visit_source, nside=args.nside)

    # You can also save html fragments suitable for embedding in other pages.
    # See https://docs.bokeh.org/en/latest/docs/user_guide/output/embed.html
    bokeh.io.save(figure, args.filename)
