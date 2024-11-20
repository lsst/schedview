from datetime import date

import astropy.utils.iers
import panel as pn
import param

from schedview.dayobs import DayObs
from schedview.examples.visittable import visit_table


class VisitTableDashboard(param.Parameterized):

    night = param.Date(
        default=date.today(),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )

    visit_origin = param.String(
        default="lsstcomcam", label="Data source", doc="Instrument name or baseline version"
    )

    @param.depends("night", "visit_origin", watch=True)
    def visit_table(self):
        ui_element = visit_table(self.visit_origin, DayObs(self.night))
        return ui_element

    def make_app(self):
        self.visit_table()

        app = pn.Column(
            pn.Param(self, parameters=["night", "visit_origin"], widgets={"night": pn.widgets.DatePicker}),
            pn.param.ParamMethod(self.visit_table, loading_indicator=True),
        )
        return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    def make_app():
        dashboard = VisitTableDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Visit Table Dashboard")
