import unittest

import numpy as np
from astropy.time import Time
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.compute.visits

try:
    from rubin_sim import maf

    HAVE_MAF = True
except ModuleNotFoundError:
    HAVE_MAF = True


class TestComputeVisits(unittest.TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = SURVEY_START_MJD
        start_time = Time(start_mjd, format="mjd")
        end_time = Time(start_mjd + 1, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, start_time, end_time)

    def test_add_coords_tuple(self):
        visits = schedview.compute.visits.add_coords_tuple(self.visits)
        self.assertEqual(len(visits["coords"].iloc[0]), 2)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_add_maf_metric(self):
        constraint = None
        visits = schedview.compute.visits.add_maf_metric(
            self.visits,
            maf.SumMetric(col="t_eff", metric_name="Total Teff"),
            "teff",
            constraint,
            "fiveSigmaDepth",
        )
        self.assertIn("teff", visits.columns)

    def test_add_instrumental_fwhm(self):
        visits = schedview.compute.visits.add_instrumental_fwhm(self.visits)
        self.assertTrue(np.all(visits.seeingFwhmEff > visits.inst_fwhm))
        self.assertTrue(np.all(visits.inst_fwhm > 0))
        self.assertIn("inst_fwhm", visits.columns)

    @unittest.skipUnless("maf" in locals(), "No maf installation")
    def test_accum_stats_by_target_band_night(self):
        stackers = [
            maf.stackers.ObservationStartDatetime64Stacker(),
            maf.stackers.TeffStacker(),
            maf.stackers.DayObsISOStacker(),
        ]

        visits = schedview.collect.read_ddf_visits(self.visit_db_fname, stackers=stackers)
        night_teff = schedview.compute.visits.accum_stats_by_target_band_night(visits)
        self.assertEqual(night_teff.index.names[0], "target_name")
        self.assertEqual(night_teff.index.names[1], "day_obs_iso8601")
        for col_name in night_teff.columns:
            self.assertTrue(col_name in "ugrizy")
