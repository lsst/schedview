import pandas as pd
import uranography.api
from bokeh.models.ui.ui_element import UIElement
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory

import schedview.collect.visits
import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def visit_map(
    visit_source: str = "3.5",
    day_obs: DayObs = DayObs.from_date("2026-03-15"),
    nside: int = 8,
    map_classes=[uranography.api.ArmillarySphere],
) -> UIElement:

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
