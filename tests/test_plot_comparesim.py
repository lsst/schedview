from datetime import datetime
from unittest import TestCase

import bokeh.models
import bokeh.plotting
import pandas as pd

import schedview.plot.comparesim


class TestPlotCompareSim(TestCase):

    def setUp(self):
        # Create test data that mimics what would come from
        # compute_obs_sim_offsets
        # Do not worry about making delta correspond to obs and sim times,
        # because it does not matter here.
        obs_times = [datetime(2030, 1, 1, hr, 0, 0) for hr in range(6)]
        sim_times = [datetime(2030, 1, 1, hr, 15, 0) for hr in range(6)]
        self.test_offsets = pd.DataFrame(
            {
                "obs_time": obs_times,
                "sim_time": sim_times,
                "sim_index": [0, 0, 0, 1, 1, 1],
                "label": ["Completed", "Completed", "Completed", "Sim 1", "Sim 1", "Sim 1"],
                "fieldRA": [10.0, 20.0, 30.0, 10.0, 20.0, 30.0],
                "fieldDec": [0.0, 10.0, 20.0, 0.0, 10.0, 20.0],
                "band": ["u", "g", "r", "u", "g", "r"],
                "delta": [0, 0, 0, 0, 0, 0],
            }
        ).set_index(["sim_index", "fieldRA", "fieldDec"])

    def test_plot_obs_vs_sim_time_basic(self):
        """Test basic functionality of plot_obs_vs_sim_time."""
        tooltips = [
            ("Observation Time", "@obs_time{%F %H:%M}"),
            ("Simulation Time", "@sim_time{%F %H:%M}"),
            ("Band", "@band"),
        ]

        result = schedview.plot.comparesim.plot_obs_vs_sim_time(self.test_offsets, tooltips)

        # Check that first child is a Select widget (sim selector)
        self.assertIsInstance(result.children[0], bokeh.models.Select)

        # Check that second child is a bokeh figure
        plot = result.children[1]
        self.assertIsInstance(plot, bokeh.plotting.figure)

        # Check that tooltips were properly set up
        self.assertGreater(len(plot.tools), 0)

        # Check that there are data points
        source = plot.renderers[0].data_source
        self.assertGreater(len(source.data["obs_time"]), 0)
