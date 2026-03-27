import unittest
from typing import Tuple

import healpy as hp
import numpy as np
import numpy.typing as npt
import pandas as pd

from schedview import DECL_COL, POINTING_COL, RA_COL
from schedview.compute.comparesim import (
    combine_completed_with_sims,
    compute_obs_sim_offsets,
    compute_offset_stats,
    find_nearest_pointing_ids,
    offsets_of_coord_band,
)

RANDOM_NUMBER_GENERATOR = np.random.default_rng(6563)


class TestOffsetOfCoordBand(unittest.TestCase):

    def setUp(self):
        self.num_test_visits = 10

        # generate a set of self.num_test_visits times separated by 500 to 600
        # seconds, and generate a dataframe self.sim_visits with those times.
        start_time = pd.Timestamp("2027-01-01 00:00:00", tz="UTC")
        time_diffs = np.random.uniform(500, 600, self.num_test_visits)
        times = [
            start_time + pd.Timedelta(seconds=np.sum(time_diffs[:i])) for i in range(self.num_test_visits)
        ]
        self.sim_visits = pd.DataFrame(
            {
                "start_timestamp": times,
                RA_COL: [10.0] * self.num_test_visits,
                DECL_COL: [0.0] * self.num_test_visits,
                "band": ["r"] * self.num_test_visits,
            }
        )

        # randomly but repeatably generate a set of self.num_test_visits
        # offsets between -60 and 60 seconds, self.offsets, and apply these to
        # self.sim_visits to get self.obs_visits
        self.offsets = RANDOM_NUMBER_GENERATOR.uniform(-60, 60, self.num_test_visits)
        self.obs_visits = self.sim_visits.copy()
        self.obs_visits["start_timestamp"] = self.obs_visits["start_timestamp"] + pd.to_timedelta(
            self.offsets, unit="s"
        )
        self.obs_visits["sim_index"] = [0] * self.num_test_visits

    def test_equal_numbers(self):
        visits = pd.concat(
            [self.sim_visits.assign(sim_index=0), self.obs_visits.assign(sim_index=1)], ignore_index=True
        )

        # Verify that we can recover the time offsets
        result = offsets_of_coord_band(0, visits, 1)
        np.testing.assert_array_almost_equal(result["delta"].to_numpy(), self.offsets, decimal=4)

        # Verify that we can reverse the sign
        result = offsets_of_coord_band(1, visits, 0)
        np.testing.assert_array_almost_equal(result["delta"].to_numpy(), -1 * self.offsets, decimal=4)

    def test_missing_some(self):
        dropped_indexes = RANDOM_NUMBER_GENERATOR.choice(len(self.sim_visits), 3, replace=False)
        kept_indexes = np.setdiff1d(np.arange(len(self.sim_visits)), dropped_indexes)
        remaining_offsets = self.offsets[kept_indexes]

        reduced_sim_visits = self.sim_visits.drop(dropped_indexes).reset_index(drop=True)

        visits = pd.concat(
            [reduced_sim_visits.assign(sim_index=0), self.obs_visits.assign(sim_index=1)], ignore_index=True
        )

        # Visits that weren't dropped should be recoverable
        result = offsets_of_coord_band(0, visits, 1)
        np.testing.assert_array_almost_equal(result["delta"].to_numpy(), remaining_offsets, decimal=4)

        # Reverse sim and obs, and see if it still works
        result = offsets_of_coord_band(1, visits, 0)
        np.testing.assert_array_almost_equal(result["delta"].to_numpy(), -1 * remaining_offsets, decimal=4)


def _generate_test_visits(
    num_visits_per_hpid_band, num_hpid_band, num_sims
) -> Tuple[pd.DataFrame, npt.NDArray, pd.DataFrame]:
    """Generate visits DataFrame for testing."""

    # Generate a pandas.DataFrame, hpid_band_df, of length
    # num_hpid_band,
    # with fieldRA, fieldDec, band, and fieldHpid corresponding to
    # fieldRA and fieldDec with healpy nside 32
    # fieldRA and fieldDec should be randomly but repeatably generate.
    # band should be randomly but repeatably selected from u, g, r, i, z, y
    nside = 32
    hpid_band_df = pd.DataFrame()
    hpid_band_df[POINTING_COL] = RANDOM_NUMBER_GENERATOR.integers(0, hp.nside2npix(nside), size=num_hpid_band)
    hpid_band_df[RA_COL], hpid_band_df[DECL_COL] = hp.pix2ang(nside, hpid_band_df[POINTING_COL], lonlat=True)

    # Generate random bands from u, g, r, i, z, y
    bands = ["u", "g", "r", "i", "z", "y"]
    hpid_band_df["band"] = RANDOM_NUMBER_GENERATOR.choice(bands, size=num_hpid_band)

    # Generate a set of simulations
    sim_dfs = []
    start_time = pd.Timestamp("2027-01-01 00:00:00", tz="UTC")
    for sim_index in range(1, num_sims + 1):
        sim_df = pd.DataFrame()
        visit_data = []
        start_timestamp = start_time

        # in this simulation, observe each hpid_band
        for _, hpid_band in hpid_band_df.iterrows():
            for time_diff in RANDOM_NUMBER_GENERATOR.uniform(500, 600, num_visits_per_hpid_band):
                start_timestamp = start_timestamp + pd.Timedelta(seconds=time_diff)
                visit_data.append(
                    {
                        "sim_index": sim_index,
                        "start_timestamp": start_timestamp,
                        RA_COL: hpid_band[RA_COL],
                        DECL_COL: hpid_band[DECL_COL],
                        "band": hpid_band["band"],
                        POINTING_COL: hpid_band[POINTING_COL],
                        "label": f"Sim {sim_index}",
                    }
                )

        sim_df = pd.DataFrame(visit_data)
        sim_dfs.append(sim_df)

    # Generate an obs_df with is similar to the first sim, but with offsets
    obs_df = sim_dfs[0].copy()
    offsets = RANDOM_NUMBER_GENERATOR.uniform(-6, 6, len(obs_df))
    obs_df["start_timestamp"] = obs_df["start_timestamp"] + pd.to_timedelta(offsets, unit="s")
    obs_df["sim_index"] = 0
    obs_df["label"] = "Completed"

    visits = pd.concat([obs_df] + sim_dfs, ignore_index=True)
    return visits, offsets, hpid_band_df


class TestComputeObsSimOffsets(unittest.TestCase):

    def setUp(self):
        self.num_visits_per_hpid_band = 5
        self.num_hpid_band = 3
        self.num_sims = 3
        self.visits, self.offsets, self.hpid_band_df = _generate_test_visits(
            self.num_visits_per_hpid_band, self.num_hpid_band, self.num_sims
        )

    def test_compute_obs_sim_offsets_basic(self):
        # Test basic functionality of compute_obs_sim_offsets
        result = compute_obs_sim_offsets(self.visits, obs_index=0)

        self.assertIsNotNone(result)
        self.assertIn("delta", result.columns)

        # Test that we recover offsets
        sim_1_result = result.loc[1, :]
        assert isinstance(sim_1_result, pd.DataFrame)
        self.assertEqual(len(self.visits.query("sim_index == 1")), len(sim_1_result))
        np.testing.assert_array_almost_equal(
            sim_1_result.sort_values(by=["sim_time"]).loc[:, "delta"].to_numpy(),
            self.offsets,
            decimal=4,
        )

        self.assertTrue(isinstance(result.index, pd.MultiIndex))
        self.assertEqual(result.index.names, ["sim_index", POINTING_COL, "band"])

        self.assertEqual(tuple(result.columns), ("obs_time", "sim_time", "delta"))
        self.assertEqual(str(result.obs_time.dtype), "datetime64[ns, UTC]")
        self.assertEqual(str(result.sim_time.dtype), "datetime64[ns, UTC]")
        self.assertEqual(str(result.delta.dtype), "float64")

        # Should have at least one entry for each simulation
        sim_indexes = result.index.get_level_values("sim_index").unique()
        assert set(sim_indexes) == set(range(self.num_sims + 1)) - set([0])


class TestComputeOffsetStats(unittest.TestCase):

    def setUp(self):
        self.num_visits_per_hpid_band = 5
        self.num_hpid_band = 3
        self.num_sims = 3
        self.visits, self.offset_dt, self.hpid_band_df = _generate_test_visits(
            self.num_visits_per_hpid_band, self.num_hpid_band, self.num_sims
        )
        self.offsets = compute_obs_sim_offsets(self.visits, obs_index=0)

    def test_compute_obs_sim_offsets_basic(self):
        offset_stats = compute_offset_stats(self.offsets, self.visits)
        assert len(offset_stats) == self.num_sims
        assert offset_stats.loc[1, "sim count"] == self.num_visits_per_hpid_band * self.num_hpid_band
        offset_dt_stats = pd.Series(self.offset_dt).describe()
        for col in offset_dt_stats.index[1:]:
            self.assertAlmostEqual(offset_dt_stats[col], offset_stats.loc[1, col], 5)


class TestFindNearestPointingIds(unittest.TestCase):

    def test_find_nearest_pointing_ids(self):
        pointing_ids = np.arange(3)
        pointing_ras = np.array([0.0, 10.0, 20.0])
        pointing_decls = np.array([0.0, 5.0, 10.0])

        # Reference pointing coordinates (ids, ra, dec) - with some offset
        ra = pointing_ras.copy()
        decl = pointing_decls + 0.1

        # Call the function
        matched_ids, match_separation = find_nearest_pointing_ids(
            ra, decl, pointing_ids, pointing_ras, pointing_decls
        )

        # Verify results - should match to nearest point
        expected_ids = np.arange(3)
        expected_separation = np.array([0.1, 0.1, 0.1])

        np.testing.assert_array_equal(matched_ids, expected_ids)
        np.testing.assert_array_almost_equal(match_separation, expected_separation, decimal=10)


class TestComputeCommonFractions(unittest.TestCase):

    def setUp(self):
        # Create a simple test visit counts DataFrame
        # This simulates what would come from count_visits_by_sim

        self.visit_counts = pd.DataFrame(
            {
                POINTING_COL: [100, 101, 102, 103, 100, 101, 102, 102],
                "band": ["u", "u", "u", "u", "g", "g", "g", "g"],
                0: [1, 1, 1, 1, 2, 2, 0, 0],
                1: [1, 1, 1, 1, 2, 2, 0, 0],
                2: [2, 2, 1, 1, 2, 2, 0, 0],
                3: [1, 1, 1, 1, 1, 1, 1, 1],
            }
        ).set_index([POINTING_COL, "band"])

        self.num_sims = len(self.visit_counts.columns) - 1

        # Create sim_labels Series
        self.sim_labels = pd.Series(
            ["Completed", "Sim 1", "Sim 2", "Sim 3"], index=[0, 1, 2, 3], name="label"
        )


class TestCombineCompletedWithSims(unittest.TestCase):

    def setUp(self):
        self.simulated_visits = pd.DataFrame(
            {
                "start_timestamp": [
                    pd.Timestamp("2027-01-01 00:00:00", tz="UTC"),
                    pd.Timestamp("2027-01-01 01:00:00", tz="UTC"),
                ],
                RA_COL: [10.0, 20.0],
                DECL_COL: [0.0, 5.0],
                "band": ["r", "g"],
                "sim_index": [1, 2],
            }
        )

        self.completed_visits = pd.DataFrame(
            {
                "start_date": ["2027-01-01 00:30:00", "2027-01-01 02:00:00"],
                "band": ["r", "g"],
                RA_COL: [10.1, 20.1],
                DECL_COL: [0.1, 5.1],
            }
        )

    def test_combine_completed_with_sims_basic(self):

        result = combine_completed_with_sims(
            simulated_visits=self.simulated_visits,
            completed_visits=self.completed_visits,
            scheduler_version="test_version",
        )

        # Check that we have the right number of rows
        self.assertEqual(len(result), 4)  # 2 simulated + 2 completed

        # Check that completed visits have correct values
        completed_rows = result.loc[result["sim_index"] == 0, :]
        self.assertEqual(len(completed_rows), 2)
        self.assertTrue(np.all(completed_rows["label"] == "Completed"))
        self.assertTrue(np.all(completed_rows["scheduler_version"] == "test_version"))
        self.assertTrue(np.all(completed_rows["config_url"] == ""))

        # Check that simulated visits are preserved
        simulated_rows = result.loc[result["sim_index"] > 0, :]
        self.assertEqual(len(simulated_rows), 2)
        self.assertTrue(np.all(simulated_rows["sim_index"].isin([1, 2])))

    def test_combine_completed_with_sims_no_completed(self):

        result = combine_completed_with_sims(
            simulated_visits=self.simulated_visits,
            completed_visits=pd.DataFrame(),
            scheduler_version="test_version",
        )

        # Should just return simulated visits
        self.assertEqual(len(result), len(self.simulated_visits))

    def test_combine_completed_with_sims_sim_index_zero_error(self):
        # Create test simulated visits with sim_index = 0 (should raise error)
        bad_simulated_visits = self.simulated_visits.copy()
        bad_simulated_visits["sim_index"].values[0] = 0

        # Test that it raises ValueError when sim_index = 0
        with self.assertRaises(ValueError):
            combine_completed_with_sims(
                simulated_visits=bad_simulated_visits,
                completed_visits=self.completed_visits,
                scheduler_version="test_version",
            )
