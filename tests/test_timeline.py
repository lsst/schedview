import asyncio
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
from astropy.time import Time

from schedview.examples.timeline import run_full_timeline_pipeline
from schedview.plot.timeline import TimelinePlotter

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


class TestTimelinePlotters(TestCase):
    num_events = 5
    rng = np.random.default_rng(6563)

    @unittest.skip("Slow and depends on real consdb and EFD")
    def test_example(self):
        ui_element = asyncio.run(run_full_timeline_pipeline("2024-12-11"))
        assert is_plottable_bokeh(ui_element)

    def test_plot(self):
        mjds = self.rng.uniform(61000.2, 61001.4, self.num_events)
        data = {
            "time": Time(mjds, format="mjd").datetime64,
            "eggs": self.rng.choice(list(string.printable), self.num_events),
        }
        plotter = TimelinePlotter(data)
        assert is_plottable_bokeh(plotter.plot)
