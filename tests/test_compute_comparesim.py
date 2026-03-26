import unittest

import healpy as hp
import numpy as np
import pandas as pd

from schedview.compute.comparesim import (
    compute_obs_sim_offsets,
    compute_offset_stats,
    offsets_of_coord_band,
)
from schedview import DECL_COL, POINTING_COL, RA_COL

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
        np.testing.assert_array_almost_equal(result["delta"].values, self.offsets, decimal=4)

        # Verify that we can reverse the sign
        result = offsets_of_coord_band(1, visits, 0)
        np.testing.assert_array_almost_equal(result["delta"].values, -1 * self.offsets, decimal=4)

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
        np.testing.assert_array_almost_equal(result["delta"].values, remaining_offsets, decimal=4)

        # Reverse sim and obs, and see if it still works
        result = offsets_of_coord_band(1, visits, 0)
        np.testing.assert_array_almost_equal(result["delta"].values, -1 * remaining_offsets, decimal=4)


def _generate_test_visits(num_visits_per_hpid_band, num_hpid_band, num_sims):
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
    obs_df["lable"] = "Completed"

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
        np.testing.assert_array_almost_equal(
            result.loc[1, :].sort_values("sim_time").loc[:, "delta"].values,
            self.offsets,
            decimal=4,
        )

        # Should have a multiindex with sim_index, fieldHpid, and band
        self.assertTrue(isinstance(result.index, pd.MultiIndex))
        self.assertEqual(result.index.names, ["sim_index", POINTING_COL, "band"])

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


if __name__ == "__main__":
    unittest.main()
