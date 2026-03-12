import unittest

import healpy as hp
import numpy as np
import pandas as pd

from schedview.compute.comparesim import (
    assign_field_hpids,
    compute_obs_sim_offsets,
    compute_offset_stats,
    offsets_of_coord_band,
)

RANDOM_NUMBER_GENERATOR = np.random.default_rng(6563)


class TestAssignFieldHpids(unittest.TestCase):

    def setUp(self):
        self.nside = 2**10

        # Pick a few random but reproducible healpix indices.
        self.sim_hpids = RANDOM_NUMBER_GENERATOR.integers(0, hp.nside2npix(self.nside), size=5)
        ra, dec = hp.pix2ang(self.nside, self.sim_hpids, lonlat=True)
        self.simulated_visits = pd.DataFrame({"fieldRA": ra, "fieldDec": dec})

        # Build completed visits based on the simulated ones.
        completed = self.simulated_visits.copy()
        # First two rows: small offset (< tolerance), so should be reassigned.
        completed.loc[0:1, "fieldRA"] += 0.001
        completed.loc[0:1, "fieldDec"] += 0.001
        # Next two rows: large offset (> tolerance), so should keep own hpid.
        completed.loc[2:3, "fieldRA"] += 1.0
        completed.loc[2:3, "fieldDec"] += 1.0
        # Add a few completely unrelated visits.
        extra_ra = np.array([10.0, 150.0, 250.0])
        extra_dec = np.array([-30.0, 0.0, 45.0])
        extra = pd.DataFrame({"fieldRA": extra_ra, "fieldDec": extra_dec})
        self.completed_visits = pd.concat([completed, extra], ignore_index=True)

        self.tolerance_deg = 0.01

    def test_assign_field_hpids_basic(self):
        sim_out, comp_out = assign_field_hpids(
            self.simulated_visits,
            self.completed_visits,
            nside=self.nside,
            coord_match_tolerance_deg=self.tolerance_deg,
            inplace=False,
        )

        # Simulated IDs should equal the original healpix indices.
        np.testing.assert_array_equal(sim_out["fieldHpid"].values, self.sim_hpids)

        # Within‑tolerance rows (0 and 1) should have the same hpid as the
        # corresponding simulated rows.
        self.assertEqual(comp_out.loc[0, "fieldHpid"], self.sim_hpids[0])
        self.assertEqual(comp_out.loc[1, "fieldHpid"], self.sim_hpids[1])

        # Rows with a large offset should retain the hpid computed from their
        # own coordinates
        self.assertNotEqual(comp_out.loc[2, "fieldHpid"], self.sim_hpids[2])
        self.assertNotEqual(comp_out.loc[3, "fieldHpid"], self.sim_hpids[3])

        # Ensure the original DataFrames are unchanged.
        self.assertNotIn("fieldHpid", self.simulated_visits.columns)
        self.assertNotIn("fieldHpid", self.completed_visits.columns)

    def test_assign_field_hpids_inplace(self):

        sim_original = self.simulated_visits.copy()
        comp_original = self.completed_visits.copy()

        sim_out, comp_out = assign_field_hpids(
            sim_original,
            comp_original,
            nside=self.nside,
            coord_match_tolerance_deg=self.tolerance_deg,
            inplace=True,
        )

        # Identity checks – the returned objects are the same as the inputs.
        self.assertIs(sim_out, sim_original)
        self.assertIs(comp_out, comp_original)

        # Verify that the hpid column now exists on the original objects.
        self.assertIn("fieldHpid", sim_original.columns)
        self.assertIn("fieldHpid", comp_original.columns)
        # Re‑use the basic assertions for correctness.
        np.testing.assert_array_equal(sim_original["fieldHpid"].values, self.sim_hpids)
        self.assertEqual(comp_original.loc[0, "fieldHpid"], self.sim_hpids[0])
        self.assertEqual(comp_original.loc[1, "fieldHpid"], self.sim_hpids[1])

    def test_assign_field_hpids_empty_completed(self):

        empty_completed = pd.DataFrame(columns=["fieldRA", "fieldDec"])
        sim_out, comp_out = assign_field_hpids(
            self.simulated_visits,
            empty_completed,
            nside=self.nside,
            coord_match_tolerance_deg=self.tolerance_deg,
            inplace=False,
        )
        # Simulated IDs must be correct.
        np.testing.assert_array_equal(sim_out["fieldHpid"].values, self.sim_hpids)
        # Completed DataFrame should remain empty but still have the column.
        self.assertTrue(comp_out.empty)
        self.assertIn("fieldHpid", comp_out.columns)


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
                "fieldRA": [10.0] * self.num_test_visits,
                "fieldDec": [0.0] * self.num_test_visits,
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
    hpid_band_df["fieldHpid"] = RANDOM_NUMBER_GENERATOR.integers(0, hp.nside2npix(nside), size=num_hpid_band)
    hpid_band_df["fieldRA"], hpid_band_df["fieldDec"] = hp.pix2ang(
        nside, hpid_band_df["fieldHpid"], lonlat=True
    )

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
                        "fieldRA": hpid_band["fieldRA"],
                        "fieldDec": hpid_band["fieldDec"],
                        "band": hpid_band["band"],
                        "fieldHpid": hpid_band["fieldHpid"],
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
        self.assertEqual(result.index.names, ["sim_index", "fieldHpid", "band"])

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


if __name__ == "__main__":
    unittest.main()
