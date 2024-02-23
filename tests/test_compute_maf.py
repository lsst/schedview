import unittest

import numpy as np
from rubin_scheduler.utils import survey_start_mjd
from rubin_sim import maf
from rubin_sim.data import get_baseline

from schedview.collect import read_opsim
from schedview.compute import compute_hpix_metric_in_bands, compute_metric_by_visit


class TestComputeMAF(unittest.TestCase):

    def test_compute_metric_by_visit(self):
        visits = read_opsim(get_baseline())
        mjd_start = survey_start_mjd()
        constraint = f"observationStartMjd BETWEEN {mjd_start + 0.5} AND {mjd_start+1.5}"
        metric = maf.TeffMetric()
        values = compute_metric_by_visit(visits, metric, constraint=constraint)
        self.assertGreater(len(values), 10)
        self.assertGreater(np.min(values), 0.0)
        self.assertLess(np.max(values), 300)

    def test_compute_hpix_metric_in_bands(self):
        visits = read_opsim(get_baseline())
        mjd_start = survey_start_mjd()
        constraint = f"observationStartMjd BETWEEN {mjd_start+0.5} AND {mjd_start+1.5}"
        metric = maf.TeffMetric()
        values = compute_hpix_metric_in_bands(visits, metric, constraint=constraint)
        self.assertGreater(len(values.keys()), 1)
        for band in values.keys():
            self.assertTrue(band in "urgizy")
            if len(values[band]) > 0:
                self.assertGreater(np.min(values[band]), 0.0)
                self.assertLess(np.max(values[band]), 300)
