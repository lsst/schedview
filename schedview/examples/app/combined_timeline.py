from datetime import date

import astropy.utils.iers
import panel as pn
import param

from schedview import DayObs
from schedview.collect.nightreport import get_night_narrative
from schedview.collect.visits import read_visits
from schedview.plot import make_timeline_scatterplots


class CombinedTimelineDashboard(param.Parameterized):

    # Parameters set in the UI
    night = param.Date(
        default=date.today(),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )
    telescope = param.String(default="Simonyi", label="Telescope", doc="Telescope name")
    visit_origin = param.String(default="lsstcomcam", label="Instrument", doc="Instrument")
    jitter = param.Boolean(default=False, label="Jitter", doc="Jitter the timelines")

    # Derived parameters
    day_obs = param.Parameter()
    log_messages = param.Parameter()
    visits = param.Parameter()

    @param.depends("night", watch=True)
    def update_day_obs(self):
        self.day_obs = DayObs(self.night)

    @param.depends("telescope", "day_obs", watch=True)
    def update_log_messages(self):
        self.log_messages = get_night_narrative(self.day_obs, self.telescope)

    @param.depends("day_obs", "visit_origin", watch=True)
    def update_visits(self):
        self.visits = read_visits(self.day_obs, self.visit_origin)

    @param.depends("log_messages", "visits", "jitter")
    def event_timeline(self):
        ui_element = make_timeline_scatterplots(
            log_messages=self.log_messages, visits=self.visits, jitter=self.jitter
        )
        return ui_element

    def make_app(self):
        app = pn.Column(
            pn.Param(
                self,
                parameters=["night", "telescope", "visit_origin", "jitter"],
                widgets={"night": pn.widgets.DatePicker},
            ),
            pn.param.ParamMethod(self.event_timeline, loading_indicator=True),
        )
        return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    def make_app():
        dashboard = CombinedTimelineDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Combined Timeline Dashboard")
