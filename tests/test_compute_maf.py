import unittest

import numpy as np
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

from schedview.collect import read_opsim

try:
    from rubin_sim import maf

    HAVE_MAF = True
    from schedview.compute import compute_hpix_metric_in_bands, compute_metric_by_visit
except ModuleNotFoundError:
    HAVE_MAF = False


class TestComputeMAF(unittest.TestCase):

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_metric_by_visit(self):
        visits = read_opsim(get_baseline())
        mjd_start = SURVEY_START_MJD
        constraint = f"observationStartMjd BETWEEN {mjd_start + 0.5} AND {mjd_start+1.5}"
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        values = compute_metric_by_visit(visits, metric, constraint=constraint)
        self.assertGreater(len(values), 10)
        self.assertGreater(np.min(values), 0.0)
        self.assertLess(np.max(values), 300)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_hpix_metric_in_bands(self):
        visits = read_opsim(get_baseline())
        mjd_start = SURVEY_START_MJD
        constraint = f"observationStartMjd BETWEEN {mjd_start+0.5} AND {mjd_start+1.5}"
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        values = compute_hpix_metric_in_bands(visits, metric, constraint=constraint)
        self.assertGreater(len(values.keys()), 1)
        for band in values.keys():
            self.assertTrue(band in "urgizy")
            if len(values[band]) > 0:
                self.assertGreater(np.min(values[band]), 0.0)
                self.assertLess(np.max(values[band]), 300)
