from datetime import date

import astropy.utils.iers
import bokeh.models
import hvplot
import panel as pn
import param
import uranography.api
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory

import schedview.collect.footprint
import schedview.plot.visitmap
from schedview.collect.visits import read_visits
from schedview.dayobs import DayObs
from schedview.plot import create_visit_table

STARTUP_VISIBLE_COLUMNS = ["observationStartMJD", "fieldRA", "fieldDec", "band"]
TABLE_WIDTH = 1024
MAP_CLASSES = [uranography.api.ArmillarySphere, uranography.api.Planisphere]


class ExampleCompoundVisitDashboard(param.Parameterized):

    night = param.Date(
        default=date(2024, 8, 5),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )
    visit_origin = param.String(
        default="lsstcomcam", label="Visit source", doc="Instrument or baseline version number"
    )

    # Derived parameters
    day_obs = param.Parameter()
    visits = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)
        self.nside = 32
        self.footprint = schedview.collect.footprint.get_footprint(self.nside)
        self.observatory = ModelObservatory(nside=self.nside, init_load_length=1)
        self.conditions = self.observatory.return_conditions()

    @param.depends("night", watch=True)
    def update_day_obs(self):
        self.day_obs = DayObs(self.night)
        self.observatory.mjd = self.day_obs.mean_local_solar_midnight.mjd
        self.conditions = self.observatory.return_conditions()

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

    @param.depends("visits")
    def visit_explorer(self):
        if self.visits is None:
            return "No visits"
        ui_element = hvplot.explorer(self.visits, kind="scatter", x="start_date", y="airmass")
        return ui_element

    @param.depends("visits")
    def visit_map(self):
        if self.visits is None:
            return "No visits"

        ui_element: bokeh.models.UIElement = schedview.plot.visitmap.plot_visit_skymaps(
            self.visits, self.footprint, self.conditions, map_classes=MAP_CLASSES
        )
        return ui_element

    def make_app(self):
        app = pn.Column(
            "<h1>Example compound visit dashboard</h1>",
            pn.Param(
                self,
                parameters=["night", "visit_origin"],
                widgets={"night": pn.widgets.DatePicker},
            ),
            "<h2>Visit parameter explorer</h2>",
            pn.param.ParamMethod(self.visit_explorer, loading_indicator=True),
            "<h2>Visit map</h2>",
            pn.param.ParamMethod(self.visit_map, loading_indicator=True),
            "<h2>Visit table</h2>",
            pn.param.ParamMethod(self.visit_table, loading_indicator=True),
        )
        return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    def make_app():
        dashboard = ExampleCompoundVisitDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Simple Example Compound Visit Dashboard")
