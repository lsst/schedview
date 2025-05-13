import asyncio
import threading
from collections import defaultdict
from datetime import date

import astropy.time
import astropy.utils.iers
import numpy as np
import pandas as pd
import panel as pn
import param

import schedview.collect.visits
from schedview import DayObs
from schedview.collect import SAL_INDEX_GUESSES
from schedview.collect.timeline import collect_timeline_data
from schedview.compute.astro import get_median_model_sky, night_events
from schedview.compute.obsblocks import compute_block_spans
from schedview.plot import make_timeline_scatterplots

IO_LOOP = asyncio.new_event_loop()
IO_THREAD = threading.Thread(target=IO_LOOP.run_forever, name="Timeline IO thread", daemon=True)

ORIGIN_TELESCOPE = defaultdict(np.array(["Simonyi"]).item, {"latiss": "AuxTel"})


class CombinedTimelineDashboard(param.Parameterized):

    # Parameters set in the UI
    evening_date = param.Date(
        default=date(2025, 4, 27),
        label="Date",
        doc="Day obs (local calendar date of sunset for the night)",
    )
    visit_origin = param.Selector(
        default="lsstcam", objects=["latiss", "lsstcam"], label="Instrument", doc="Instrument"
    )

    # Derived parameters
    day_obs = param.Parameter()
    events = param.Parameter()
    archive_uri = "s3://rubin:rubin-scheduler-prenight/opsim/"

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

    @param.depends("day_obs", "visit_origin", watch=True)
    def update_events(self):
        day_obs = self.day_obs
        assert isinstance(day_obs, DayObs)

        telescope = ORIGIN_TELESCOPE[self.visit_origin]

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
                visit_origin=visit_origin,
                visits=True,
                log_messages=True,
                scheduler_dependencies=True,
                scheduler_configuration=True,
                block_status=True,
                scheduler_snapshots=True,
            )
        )

        if len(events["block_status"]) > 0:
            events["block_spans"] = compute_block_spans(events["block_status"])
        events["model_sky"] = get_median_model_sky(day_obs)
        events["sun"] = night_events(day_obs.date)

        completed_visits = schedview.collect.visits.read_visits(
            day_obs, visit_origin, stackers=schedview.collect.visits.NIGHT_STACKERS
        )
        if len(completed_visits) > 0:
            completed_visits["start_timestamp"] = pd.to_datetime(
                completed_visits["start_timestamp"], format="ISO8601"
            )
            if completed_visits["start_timestamp"].dt.tz is None:
                completed_visits["start_timestamp"] = completed_visits["start_timestamp"].dt.tz_localize(
                    "UTC"
                )

            obs_start_time = (
                astropy.time.Time(completed_visits.start_timestamp.min())
                if len(completed_visits) > 0
                else day_obs.start
            )

            ts_config_ocs_version = schedview.collect.efd.get_version_at_time("ts_config_ocs", obs_start_time)
            sal_indexes = schedview.collect.efd.SAL_INDEX_GUESSES[visit_origin]
            opsim_config_script = self._run_async_io(
                schedview.collect.get_scheduler_config(ts_config_ocs_version, telescope, obs_start_time)
            )
            completed_visits["filter"] = completed_visits["band"]
            completed_visits["sim_date"] = None
            completed_visits["sim_index"] = 0
            completed_visits["label"] = "Completed"
            completed_visits["opsim_config_branch"] = ts_config_ocs_version
            completed_visits["opsim_config_repository"] = None
            completed_visits["opsim_config_script"] = opsim_config_script
            completed_visits["scheduler_version"] = schedview.collect.efd.get_version_at_time(
                "rubin_scheduler", obs_start_time
            )
            completed_visits["sim_runner_kwargs"] = {}

        simulated_visits = schedview.collect.multisim.read_multiple_opsims(
            self.archive_uri,
            day_obs.start,
            day_obs.mjd,
            stackers=schedview.collect.visits.NIGHT_STACKERS,
            telescope=telescope,
        ).query(f'sim_date == "{day_obs}"')
        visits = pd.concat([completed_visits, simulated_visits])
        events["visits"] = visits

        self.events = events

    @param.depends("events")
    def event_timeline(self):
        events = self.events
        if events is None:
            events = {}

        assert isinstance(events, dict)

        # Extract visits from **events to avoid confusing type checking.
        visits = events["visits"]
        del events["visits"]

        sim_labels = visits["label"].unique()
        sim_color_mapper, sim_color_dict, sim_marker_mapper, sim_hatch_dict = (
            schedview.plot.multisim.generate_sim_indicators(sim_labels)
        )
        band_column = schedview.util.band_column(visits)
        band_color_transform = schedview.plot.colors.make_band_cmap(
            band_column, bands=visits[band_column].unique()
        ).transform

        param_plot_kwargs = {
            "show_column_selector": True,
            "show_sim_selector": True,
            "size": 10,
            "color_transform": band_color_transform,
            "marker_transform": sim_marker_mapper,
        }

        ui_element = make_timeline_scatterplots(
            visits=visits, user_param_plot_kwargs=param_plot_kwargs, **events
        )

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
        dashboard = CombinedTimelineDashboard()
        return dashboard.make_app()

    pn.serve(make_app, title="Combined Timeline Dashboard")
