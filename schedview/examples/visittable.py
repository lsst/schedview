import argparse

import astropy.utils.iers
import bokeh.io
import pandas as pd
from bokeh.models.ui.ui_element import UIElement

import schedview.collect.visits
import schedview.plot
from schedview.dayobs import DayObs

STARTUP_VISIBLE_COLUMNS = ["observationStartMJD", "fieldRA", "fieldDec", "filter"]
TABLE_WIDTH = 1024


def make_visit_table(
    night: str = "2026-03-15",
    visit_source: str = "3.5",
) -> UIElement:

    day_obs: DayObs = DayObs.from_date(night)
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    figure: UIElement = schedview.plot.create_visit_table(
        visits, visible_column_names=STARTUP_VISIBLE_COLUMNS, width=TABLE_WIDTH
    )
    return figure


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="visittable", description="Write an html file with a visit table.")
    parser.add_argument("filename", type=str, help="output file name")
    parser.add_argument("night", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    figure = make_visit_table(args.night, args.visit_source)

    # You can also save html fragments suitable for embedding in other pages
    # See https://docs.bokeh.org/en/latest/docs/user_guide/output/embed.html
    bokeh.io.save(figure, args.filename)
