import unittest

import numpy as np
from lsst.resources import ResourcePath
from rubin_scheduler.utils import survey_start_mjd
from rubin_sim import maf
from rubin_sim.data import get_baseline

from schedview.compute import compute_metric_by_visit


class TestComputeMAF(unittest.TestCase):

    def test_compute_metric_by_visit(self):
        visits_rp = ResourcePath(get_baseline())
        mjd_start = survey_start_mjd()
        constraint = f"observationStartMjd BETWEEN {mjd_start} AND {mjd_start+1}"
        metric = maf.TeffMetric()
        values = compute_metric_by_visit(visits_rp, metric, constraint=constraint)
        self.assertGreater(len(values), 10)
        self.assertGreater(np.min(values), 0.0)
        self.assertLess(np.max(values), 300)
