from datetime import date

import astropy.utils.iers
import panel as pn
import param

from schedview import DayObs
from schedview.collect import get_night_narrative
from schedview.plot import make_timeline_scatterplots


class EventTimelineDashboard(param.Parameterized):

    night = param.Date(
        default=date.today(),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )

    telescope = param.String(default="Simonyi", label="Telescope", doc="Telescope name")

    jitter = param.Boolean(default=False, label="Jitter", doc="Jitter the timelines")

    day_obs = param.Parameter()

    log_messages = param.Parameter()

    @param.depends("night", watch=True)
    def update_day_obs(self):
        self.day_obs = DayObs(self.night)

    @param.depends("telescope", "day_obs", watch=True)
    def update_log_messages(self):
        self.log_messages = get_night_narrative(self.day_obs, self.telescope)

    @param.depends("log_messages", "jitter")
    def event_timeline(self):
        ui_element = make_timeline_scatterplots(log_messages=self.log_messages, jitter=self.jitter)
        return ui_element

    def make_app(self):
        app = pn.Column(
            pn.Param(
                self, parameters=["night", "telescope", "jitter"], widgets={"night": pn.widgets.DatePicker}
            ),
            pn.param.ParamMethod(self.event_timeline, loading_indicator=True),
        )
        return app


if __name__ == "__main__":
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    def make_app():
        dashboard = EventTimelineDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Event Timeline Dashboard")
