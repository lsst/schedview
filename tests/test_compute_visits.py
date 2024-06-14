import unittest

import numpy as np
from astropy.time import Time
from rubin_scheduler.utils import survey_start_mjd
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.compute.visits

try:
    from rubin_sim import maf
except ModuleNotFoundError:
    pass


class TestComputeVisits(unittest.TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = survey_start_mjd()
        start_time = Time(start_mjd, format="mjd")
        end_time = Time(start_mjd + 1, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, start_time, end_time)

    def test_add_coords_tuple(self):
        visits = schedview.compute.visits.add_coords_tuple(self.visits)
        self.assertEqual(len(visits["coords"].iloc[0]), 2)

    @unittest.skipUnless("maf" in locals(), "No maf installation")
    def test_add_maf_metric(self):
        constraint = None
        visits = schedview.compute.visits.add_maf_metric(
            self.visits, maf.TeffMetric(), "teff", constraint, "fiveSigmaDepth"
        )
        self.assertIn("teff", visits.columns)

    def test_add_instrumental_fwhm(self):
        visits = schedview.compute.visits.add_instrumental_fwhm(self.visits)
        self.assertTrue(np.all(visits.seeingFwhmEff > visits.inst_fwhm))
        self.assertTrue(np.all(visits.inst_fwhm > 0))
        self.assertIn("inst_fwhm", visits.columns)

    @unittest.skipUnless("maf" in locals(), "No maf installation")
    def test_accum_teff_by_night(self):
        stackers = [
            maf.stackers.ObservationStartDatetime64Stacker(),
            maf.stackers.TeffStacker(),
            maf.stackers.DayObsISOStacker(),
        ]

        visits = schedview.collect.read_ddf_visits(self.visit_db_fname, stackers=stackers)
        night_teff = schedview.compute.visits.accum_teff_by_night(visits)
        self.assertEqual(night_teff.index.names[0], "target")
        self.assertEqual(night_teff.index.names[1], "day_obs_iso8601")
        for col_name in night_teff.columns:
            self.assertTrue(col_name in "ugrizy")
