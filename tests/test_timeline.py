import asyncio
import json
import os
import string
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import astropy.utils.iers
import bokeh
import bokeh.io
import bokeh.models
import bokeh.plotting
import numpy as np
import pandas as pd
from astropy.time import Time
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

from schedview.collect import read_opsim
from schedview.compute.astro import get_median_model_sky, night_events
from schedview.dayobs import DayObs
from schedview.examples.timeline import run_full_timeline_pipeline
from schedview.plot.timeline import (
    BlockSpanTimelinePlotter,
    BlockStatusTimelinePlotter,
    LogMessageTimelinePlotter,
    ModelSkyTimelinePlotter,
    SchedulerConfigurationTimelinePlotter,
    SchedulerDependenciesTimelinePlotter,
    SchedulerStapshotTimelinePlotter,
    ScriptQueueLogeventScriptSpanTimelinePlotter,
    ScriptQueueLogeventScriptTimelinePlotter,
    SunTimelinePlotter,
    TimelinePlotter,
    VisitTimelinePlotter,
)

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

WRITE_TIMEOUT_SECONDS = 20


def is_plottable_bokeh(plot):
    temp_dir = TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    saved_html_fname = str(temp_path.joinpath(f"can_verify_plot_test_{time.time()}.html"))
    bokeh.plotting.output_file(filename=saved_html_fname, title="This Test Page")
    bokeh.io.save(plot, filename=saved_html_fname)
    waited_time_seconds = 0
    while waited_time_seconds < WRITE_TIMEOUT_SECONDS and not os.path.isfile(saved_html_fname):
        time.sleep(1)

    return os.path.isfile(saved_html_fname)


def to_list_of_dicts(**dict_of_lists):
    # The EFD returns lists of dicts, but these are irritating to make,
    # so convert from easier assignment with args to this function.
    return pd.DataFrame(dict_of_lists).to_dict(orient="records")


class TestTimelinePlotters(TestCase):
    num_events = 5
    rng = np.random.default_rng(6563)

    @unittest.skip("Slow and depends on real consdb and EFD")
    def test_example(self):
        ui_element = asyncio.run(run_full_timeline_pipeline("2024-12-11"))
        assert is_plottable_bokeh(ui_element)

    def test_generic_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            eggs=self.rng.choice(list(string.printable), num_events),
        )
        plotter = TimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_message_log_plotter(self):
        num_events = 4
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            date_added=Time(mjds, format="mjd").datetime64,
            message_text=self.rng.choice(list(string.printable), num_events),
            time_lost_type=["fault"] * num_events,
            is_human=[True] * num_events,
            components=[[""], ["foo"], ["foo", "bar"], ["foo", "bar", "baz"]],
        )
        plotter = LogMessageTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_message_log_span_plotter(self):
        num_events = 4
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            date_added=Time(mjds, format="mjd").datetime64,
            message_text=self.rng.choice(list(string.printable), num_events),
            time_lost_type=["fault"] * num_events,
            is_human=[True] * num_events,
            components=[[""], ["foo"], ["foo", "bar"], ["foo", "bar", "baz"]],
            date_begin=Time(mjds - 0.01, format="mjd").iso,
            date_end=Time(mjds + 0.01, format="mjd").iso,
        )
        plotter = LogMessageTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_sched_dep_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            eggs=self.rng.choice(list(string.printable), num_events),
        )
        plotter = SchedulerDependenciesTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_sched_config_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            eggs=self.rng.choice(list(string.printable), num_events),
        )
        plotter = SchedulerConfigurationTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_sched_snapshot_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            eggs=self.rng.choice(list(string.printable), num_events),
            url=["http://example.com"] * num_events,
        )
        plotter = SchedulerStapshotTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_block_status_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            definition=[json.dumps("some stuff")] * num_events,
            status=self.rng.choice(["STARTED", "EXECUTING", "COMPLETED", "ERRER"], num_events),
        )
        plotter = BlockStatusTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    def test_block_span_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            time=Time(mjds, format="mjd").datetime64,
            definition=[json.dumps("some stuff")] * num_events,
            status=self.rng.choice(["STARTED", "EXECUTING", "COMPLETED", "ERRER"], num_events),
            start_time=Time(mjds - 0.01, format="mjd").iso,
            end_time=Time(mjds + 0.01, format="mjd").iso,
            end=[""] * num_events,
        )
        plotter = BlockSpanTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    @unittest.skip("Broken, because opsim does not have consdb cols.")
    def test_visit_timeline_plotter(self):
        visit_db_fname = get_baseline()
        start_mjd = SURVEY_START_MJD
        start_time = Time(start_mjd + 0.5, format="mjd")
        end_time = Time(start_mjd + 1.5, format="mjd")
        visits = read_opsim(visit_db_fname, start_time, end_time).head()
        plotter = VisitTimelinePlotter(visits)
        assert is_plottable_bokeh(plotter.plot)

    def test_sun_timeline_plotter(self):
        events = night_events(DayObs.from_date("2025-01-01").date)
        plotter = SunTimelinePlotter(events)
        assert is_plottable_bokeh(plotter.plot)

    def test_model_sky_timeline_plotter(self):
        median_model_sky = get_median_model_sky(DayObs.from_date("2025-01-01"))
        plotter = ModelSkyTimelinePlotter(median_model_sky)
        assert is_plottable_bokeh(plotter.plot)

    @unittest.skip("Needs lsst.ts module missing from test environment")
    def test_scipts_logevent_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            first_logevent_time=Time(mjds, format="mjd").datetime64,
            striptState=self.rng.choice(np.arange(6), num_events),
        )
        plotter = ScriptQueueLogeventScriptTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)

    @unittest.skip("Needs lsst.ts module missing from test environment")
    def test_scipts_logevent_span_timeline_plotter(self):
        num_events = 3
        mjds = self.rng.uniform(61000.2, 61001.4, num_events)
        data = to_list_of_dicts(
            first_logevent_time=Time(mjds, format="mjd").datetime64,
            striptState=self.rng.choice(np.arange(6), num_events),
            start_time=Time(mjds - 0.01, format="mjd").iso,
            end_time=Time(mjds + 0.01, format="mjd").iso,
        )
        plotter = ScriptQueueLogeventScriptSpanTimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)
