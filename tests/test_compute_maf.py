from functools import partial
import unittest

import numpy as np
import pandas as pd
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline
from rubin_sim import maf

from schedview import DayObs
from schedview.collect import read_opsim
from schedview.compute.maf import make_metric_progress_df

try:
    from rubin_sim import maf

    HAVE_MAF = True
    from schedview.compute import (
        compute_hpix_metric_in_bands,
        compute_metric_by_visit,
        compute_scalar_metric_at_one_mjd,
        compute_scalar_metric_at_mjds,
        compute_mixed_scalar_metric,
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

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_scalar_metric_at_mjds(self):
        visits = self.visits
        # Use dates where some have visits and some don't
        mjds = SURVEY_START_MJD + np.arange(5) - 1
        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        slicer = maf.UniSlicer()

        result = compute_scalar_metric_at_mjds(mjds, visits, slicer, metric)

        self.assertIsInstance(result, pd.Series)
        self.assertLessEqual(len(result), len(mjds[mjds > 0]))
        self.assertEqual(result.name, "Total Teff")

        # All values should be numeric and non-negative
        for value in result.values:
            self.assertIsInstance(value, (int, float))
            self.assertGreaterEqual(value, 0.0)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_compute_mixed_scalar_metric(self):

        # Use the first month or so of the baseline as the test end visits
        end_visits = self.visits[self.visits.observationStartMJD < SURVEY_START_MJD + 30]

        # Modify the end visits to create a sample start visits.
        start_visits = end_visits.sample(n=100, random_state=42).copy()

        # Shift observationStartDate by random amounts less than 0.0001 days,
        # which is just under 9 seconds.
        np.random.seed(42)
        start_visits["observationStartMJD"] = start_visits["observationStartMJD"] + np.random.uniform(
            -0.0001, 0.0001, len(start_visits)
        )

        transition_mjds = SURVEY_START_MJD + np.arange(1, 6) * 2

        metric = maf.SumMetric(col="t_eff", metric_name="Total Teff")
        slicer = maf.UniSlicer()

        result = compute_mixed_scalar_metric(
            start_visits, end_visits, transition_mjds, mjd=SURVEY_START_MJD + 30, slicer=slicer, metric=metric
        )

        self.assertIsInstance(result, pd.Series)
        self.assertEqual(result.name, "Total Teff")

        # Check that result index is a subset of transition_mjds (some may fail due to no visits)
        self.assertTrue(set(result.index).issubset(set(transition_mjds)))

        # All values should be numeric and non-negative
        for value in result.values:
            self.assertIsInstance(value, (int, float))
            self.assertGreaterEqual(value, 0.0)

    @unittest.skipUnless(HAVE_MAF, "No maf installation")
    def test_make_metric_progress_df(self):
        # Create some sample data for completed and baseline visits
        # Using a subset of the baseline visits for both
        current_mjd = int(SURVEY_START_MJD) + 10.5
        completed_visits = self.visits[self.visits.observationStartMJD < current_mjd]
        start_dayobs = DayObs.from_time(SURVEY_START_MJD + 1)
        extrapolation_dayobs = DayObs.from_time(current_mjd + 3)

        # Test with default frequency
        result = make_metric_progress_df(
            completed_visits=completed_visits,
            baseline_visits=self.visits,
            start_dayobs=start_dayobs,
            extrapolation_dayobs=extrapolation_dayobs,
            slicer_factory=maf.UniSlicer,
            metric_factory=partial(maf.CountMetric, col="observationStartMJD", metric_name="count"),
            freq="D",
        )
        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "mjd"
        assert len(result) > 0
        assert "date" in result.columns
        assert np.all(result.loc[:, "baseline"].values >= 0)
        for column in ("snapshot", "chimera"):
            assert np.all(result.loc[:current_mjd, column] >= 0)
            assert np.all(np.isnan(result.loc[current_mjd:, column]))

        result = make_metric_progress_df(
            completed_visits=completed_visits,
            baseline_visits=self.visits,
            start_dayobs=start_dayobs,
            extrapolation_dayobs=extrapolation_dayobs,
            slicer_factory=partial(maf.HealpixSlicer, nside=8, verbose=False),
            metric_factory=partial(maf.CountExplimMetric, metric_name="fO"),
            summary_metric_factory=partial(
                maf.FOArea,
                nside=8,
                norm=False,
                metric_name="fOArea",
                asky=18000,
                n_visit=5,
                badval=0,
            ),
            freq="D",
        )
        assert isinstance(result, pd.DataFrame)
        assert result.index.name == "mjd"
        assert len(result) > 0
        assert "date" in result.columns
        assert np.all(result.loc[:, "baseline"].values >= 0)
        for column in ("snapshot", "chimera"):
            assert np.all(result.loc[:current_mjd, column] >= 0)
            assert np.all(np.isnan(result.loc[current_mjd:, column]))
