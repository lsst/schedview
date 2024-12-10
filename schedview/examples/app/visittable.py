from datetime import date

import astropy.utils.iers
import panel as pn
import param

from schedview.collect.visits import read_visits
from schedview.dayobs import DayObs
from schedview.plot import create_visit_table

STARTUP_VISIBLE_COLUMNS = ["observationStartMJD", "fieldRA", "fieldDec", "filter"]
TABLE_WIDTH = 1024


class VisitTableDashboard(param.Parameterized):

    night = param.Date(
        default=date.today(),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )
    visit_origin = param.String(
        default="lsstcomcam", label="Visit source", doc="Instrument or baseline version number"
    )

    # Derived parameters
    day_obs = param.Parameter()
    visits = param.Parameter()

    @param.depends("night", watch=True)
    def update_day_obs(self):
        self.day_obs = DayObs(self.night)

    @param.depends("day_obs", "visit_origin", watch=True)
    def update_visits(self):
        self.visits = read_visits(self.day_obs, self.visit_origin)

    @param.depends("visits")
    def visit_table(self):
        if self.visits is None:
            return "No visits"
        ui_element = create_visit_table(
            visits=self.visits, visible_column_names=STARTUP_VISIBLE_COLUMNS, width=TABLE_WIDTH
        )
        return ui_element

    def make_app(self):
        app = pn.Column(
            pn.Param(
                self,
                parameters=["night", "visit_origin"],
                widgets={"night": pn.widgets.DatePicker},
            ),
            pn.param.ParamMethod(self.visit_table, loading_indicator=True),
        )
        return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    def make_app():
        dashboard = VisitTableDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Tabular Visit Dashboard")
