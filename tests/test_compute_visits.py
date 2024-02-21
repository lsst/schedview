import unittest

from astropy.time import Time
from rubin_scheduler.utils import survey_start_mjd
from rubin_sim import maf
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.compute.visits


class TestComputeVisits(unittest.TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = survey_start_mjd()
        start_time = Time(start_mjd, format="mjd")
        end_time = Time(start_mjd + 1, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, start_time, end_time)

    def test_add_day_obs(self):
        visits = schedview.compute.visits.add_day_obs(self.visits)
        self.assertEqual(visits.columns[1], "day_obs_mjd")
        self.assertEqual(visits.columns[2], "day_obs_date")
        self.assertEqual(visits.columns[3], "day_obs_iso8601")

    def test_add_coords_tuple(self):
        visits = schedview.compute.visits.add_coords_tuple(self.visits)
        self.assertEqual(len(visits["coords"].iloc[0]), 2)

    def test_add_maf_metric(self):
        constraint = None
        visits = schedview.compute.visits.add_maf_metric(
            self.visits, maf.TeffMetric(), "teff", self.visit_db_fname, constraint, "fiveSigmaDepth"
        )
        self.assertIn("teff", visits.columns)
