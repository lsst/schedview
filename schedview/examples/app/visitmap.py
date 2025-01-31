import astropy.utils.iers
import panel as pn

from schedview.dayobs import DayObs
from schedview.examples.visitmap import make_visit_map

DEFAULT_VISIT_SOURCE = "3.5"


def make_visitmap_app():
    initial_date = DayObs.from_date("2026-12-01").date
    date_widget = pn.widgets.DatePicker(name="Date (evening)", value=initial_date)
    visit_source_widget = pn.widgets.Select(
        name="Visit source", options=["lsstcomcam", "latiss", "3.4", "3.5", "4.0"], value=DEFAULT_VISIT_SOURCE
    )

    app = pn.Column(
        pn.Row(visit_source_widget, date_widget),
        pn.bind(make_visit_map, iso_date=date_widget, visit_source=visit_source_widget),
    ).servable()
    return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    pn.extension()
    app = make_visitmap_app()
    pn.serve(app, start=True)
