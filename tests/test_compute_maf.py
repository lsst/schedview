import unittest

import numpy as np
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline
from rubin_sim import maf

from schedview.collect import read_opsim

try:
    from rubin_sim import maf

    HAVE_MAF = True
    from schedview.compute import (
        compute_hpix_metric_in_bands,
        compute_metric_by_visit,
        compute_scalar_metric_at_one_mjd,
    )
except ModuleNotFoundError:
    HAVE_MAF = False


class TestComputeMAF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # If maf is not installed, we are not doing any tests, so
        # do not bother reading cls.visits.
        if HAVE_MAF:
            cls.visits = read_opsim(get_baseline())
        else:
            cls.visits = None

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_metric_by_visit(self):
        visits = self.visits
        mjd_start = SURVEY_START_MJD
        constraint = f"observationStartMjd BETWEEN {mjd_start + 0.5} AND {mjd_start+1.5}"
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        values = compute_metric_by_visit(visits, metric, constraint=constraint)
        self.assertGreater(len(values), 10)
        self.assertGreater(np.min(values), 0.0)
        self.assertLess(np.max(values), 300)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_hpix_metric_in_bands(self):
        visits = self.visits.query(f"observationStartMJD < {SURVEY_START_MJD + 1.5}")
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        values = compute_hpix_metric_in_bands(visits, metric)
        self.assertGreater(len(values.keys()), 1)
        for band in values.keys():
            self.assertTrue(band in "urgizy")
            if len(values[band]) > 0:
                self.assertGreater(np.min(values[band]), 0.0)
                self.assertLess(np.max(values[band]), 300)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_scalar_metric_at_one_mjd(self):
        visits = self.visits
        mjd_start = SURVEY_START_MJD
        # Use a date that should have visits
        mjd = mjd_start + 5.0
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        slicer = maf.UniSlicer()

        result = compute_scalar_metric_at_one_mjd(mjd, visits, slicer, metric)

        self.assertIsInstance(result, dict)
        self.assertIn("Total Teff", result)
        self.assertIsInstance(result["Total Teff"], (int, float))
        self.assertGreaterEqual(result["Total Teff"], 0.0)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_scalar_metric_at_one_mjd_with_summary_metric(self):
        visits = self.visits
        mjd_start = SURVEY_START_MJD
        # Use a date that should have visits
        mjd = mjd_start + 5.0
        metric = maf.CountMetric(col="t_eff", metric_name="Count Teff")
        slicer = maf.UniSlicer()
        summary_metric = maf.SumMetric(col="t_eff", metric_name="Sum Teff")

        result = compute_scalar_metric_at_one_mjd(mjd, visits, slicer, metric, summary_metric=summary_metric)

        self.assertIsInstance(result, dict)
        self.assertIn("Sum Teff", result)
        self.assertIsInstance(result["Sum Teff"], (int, float))
        self.assertGreaterEqual(result["Sum Teff"], 0.0)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_scalar_metric_at_one_mjd_no_visits(self):
        visits = self.visits
        # Use a date that should have no visits
        mjd = SURVEY_START_MJD - 10.0
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        slicer = maf.UniSlicer()

        with self.assertRaises(ValueError):
            compute_scalar_metric_at_one_mjd(mjd, visits, slicer, metric)
