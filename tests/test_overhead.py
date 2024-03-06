import unittest

import bokeh
from astropy.time import Time
from rubin_scheduler.data import get_baseline
from rubin_scheduler.utils import survey_start_mjd

import schedview.collect
import schedview.compute.visits
import schedview.plot


class TestOverhead(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.visit_db_fname = get_baseline()
        start_mjd = survey_start_mjd()
        cls.start_time = Time(start_mjd + 0.5, format="mjd")
        cls.end_time = Time(start_mjd + 1.5, format="mjd")
        cls.visits = schedview.collect.read_opsim(cls.visit_db_fname, cls.start_time, cls.end_time)
        cls.visits = schedview.compute.visits.add_overhead(cls.visits)

    def test_overhead_summary(self):
        overhead_summary = schedview.compute.visits.compute_overhead_summary(
            self.visits, self.start_time.mjd, self.end_time.mjd
        )
        summary = schedview.plot.overhead.create_overhead_summary_table(overhead_summary)
        self.assertIsInstance(summary, str)

    def test_create_overhead_histogram(self):
        figure = schedview.plot.overhead.create_overhead_histogram(self.visits)
        self.assertIsInstance(figure, bokeh.models.plots.Plot)

    def test_plot_overhead_vs_slew_distance(self):
        figure = schedview.plot.overhead.plot_overhead_vs_slew_distance(self.visits)
        self.assertIsInstance(figure, bokeh.models.plots.Plot)
