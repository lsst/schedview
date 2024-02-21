from unittest import TestCase

import bokeh
from astropy.time import Time
from rubin_scheduler.data import get_baseline
from rubin_scheduler.utils import survey_start_mjd

import schedview.collect
import schedview.plot


class TestPlotVisits(TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = survey_start_mjd()
        self.start_time = Time(start_mjd + 0.5, format="mjd")
        self.end_time = Time(start_mjd + 1.5, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, self.start_time, self.end_time)

    def test_plot_visit_param_vs_time(self):
        plot = schedview.plot.plot_visit_param_vs_time(self.visits, "seeingFwhmEff")
        self.assertIsInstance(plot, bokeh.models.plots.Plot)
