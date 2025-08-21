import unittest

from astropy.time import Time
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.compute.visits
import schedview.plot


class TestSvSummary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.visit_db_fname = get_baseline()
        start_mjd = SURVEY_START_MJD
        cls.start_time = Time(start_mjd + 0.5, format="mjd")
        cls.end_time = Time(start_mjd + 1.5, format="mjd")
        cls.visits = schedview.collect.read_opsim(cls.visit_db_fname, cls.start_time, cls.end_time)
        cls.visits = schedview.compute.visits.add_overhead(cls.visits)

    def test_sv_summary(self):
        sv_summary = schedview.compute.visits.compute_sv_summary(
            self.visits, self.start_time.mjd, self.end_time.mjd
        )
        summary = schedview.plot.overhead.create_sv_summary_table(sv_summary)
        self.assertIsInstance(summary, str)
