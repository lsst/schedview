from unittest import TestCase

import bokeh
import bokeh.models
from astropy.time import Time
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.plot


class TestPlotVisits(TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = SURVEY_START_MJD
        self.start_time = Time(start_mjd + 0.5, format="mjd")
        self.end_time = Time(start_mjd + 1.5, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, self.start_time, self.end_time)

    def test_plot_visit_param_vs_time(self):
        plot = schedview.plot.plot_visit_param_vs_time(self.visits, "seeingFwhmEff")
        self.assertIsInstance(plot, bokeh.models.plots.Plot)

    def test_create_visit_table(self):
        plot = schedview.plot.create_visit_table(self.visits, show=False)
        self.assertIsInstance(plot, bokeh.models.ui.ui_element.UIElement)
