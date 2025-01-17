import datetime

import astropy.utils.iers
import panel as pn
from rubin_scheduler.utils import SURVEY_START_MJD

from schedview.examples.visitmap import make_visit_map

VISIT_SOURCE_OPTIONS = ["lsstcomcam", "latiss", "3.4", "3.5", "4.0"]
DEFAULT_VISIT_SOURCE = "4.0"
DEFAULT_DATE = datetime.date(1858, 11, 17) + datetime.timedelta(days=int(SURVEY_START_MJD))


def make_visitmap_app() -> pn.viewable.Viewable:
    date_widget = pn.widgets.DatePicker(name="Date (evening)", value=DEFAULT_DATE)
    visit_source_widget = pn.widgets.Select(
        name="Visit source", options=VISIT_SOURCE_OPTIONS, value=DEFAULT_VISIT_SOURCE
    )

    app = pn.Column(
        pn.Row(visit_source_widget, date_widget),
        pn.bind(make_visit_map, iso_date=date_widget, visit_source=visit_source_widget),
    ).servable()
    assert isinstance(app, pn.viewable.Viewable)
    return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    pn.extension()
    app: pn.viewable.Viewable = make_visitmap_app()
    pn.serve(app, start=True)
