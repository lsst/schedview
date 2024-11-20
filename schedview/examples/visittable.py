import pandas as pd
from bokeh.models.ui.ui_element import UIElement

import schedview.collect.visits
import schedview.plot
from schedview.dayobs import DayObs


def visit_table(
    visit_source: str = "3.5",
    day_obs: DayObs = DayObs.from_date("2026-03-15"),
    visible_columns: list[str] = ["observationStartMJD", "fieldRA", "fieldDec", "filter"],
) -> UIElement:
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    figure: UIElement = schedview.plot.create_visit_table(
        visits, visible_column_names=visible_columns, width=1024
    )
    return figure
