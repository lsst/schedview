import asyncio
import threading
from datetime import date

import astropy.utils.iers
import panel as pn
import param

from schedview import DayObs
from schedview.collect import SAL_INDEX_GUESSES
from schedview.collect.timeline import collect_timeline_data
from schedview.compute.astro import get_median_model_sky, night_events
from schedview.compute.obsblocks import compute_block_spans
from schedview.plot.timeline import make_multitimeline

IO_LOOP = asyncio.new_event_loop()
IO_THREAD = threading.Thread(target=IO_LOOP.run_forever, name="Timeline IO thread", daemon=True)


class EventTimelineDashboard(param.Parameterized):

    # Parameters set in the UI
    evening_date = param.Date(
        default=date(2024, 12, 10),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )
    telescope = param.String(default="Simonyi", label="Telescope", doc="Telescope name")
    visit_origin = param.String(default="lsstcomcam", label="Instrument", doc="Instrument")

    # Derived parameters
    day_obs = param.Parameter()
    events = param.Parameter()

    def _run_async_io(self, io_coroutine):
        # Run the async io (needed for the EFD) in a separate thread and
        # block while waiting for it to finish.
        # This will avoid issues with the panel event loop.
        # See https://stackoverflow.com/a/74710015
        if not IO_THREAD.is_alive():
            IO_THREAD.start()

        result = asyncio.run_coroutine_threadsafe(io_coroutine, IO_LOOP).result()

        return result

    @param.depends("evening_date", watch=True)
    def update_day_obs(self):
        evening_date = self.evening_date
        assert isinstance(evening_date, date)
        self.day_obs = DayObs(evening_date)

    @param.depends("telescope", "day_obs", "visit_origin", watch=True)
    def update_events(self):
        day_obs = self.day_obs
        assert isinstance(day_obs, DayObs)

        telescope = self.telescope

        visit_origin = self.visit_origin
        assert isinstance(visit_origin, str)

        sal_indexes = tuple(SAL_INDEX_GUESSES[visit_origin])

        # The EFD queries called by collect_timeline_data run
        # asynchronously, and interactions with panel's io loop
        # are subtle.
        # Call the async loop in a separate thread, and block until
        # it's done.
        # See https://stackoverflow.com/a/74710015
        events = self._run_async_io(
            collect_timeline_data(
                day_obs,
                sal_indexes=sal_indexes,
                telescope=telescope,
                log_messages=True,
                scheduler_dependencies=True,
                scheduler_configuration=True,
                block_status=True,
                scheduler_snapshots=True,
            )
        )

        events["block_spans"] = compute_block_spans(events["block_status"])
        events["model_sky"] = get_median_model_sky(day_obs)
        events["sun"] = night_events(day_obs.date)
        self.events = events

    @param.depends("events")
    def event_timeline(self):
        events = self.events
        if events is None:
            events = {}

        assert isinstance(events, dict)
        ui_element = make_multitimeline(**events)

        return ui_element

    def make_app(self):
        self.param.trigger("evening_date")
        app = pn.Column(
            pn.Param(
                self,
                parameters=["evening_date", "telescope", "visit_origin"],
                widgets={"evening_date": pn.widgets.DatePicker},
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
