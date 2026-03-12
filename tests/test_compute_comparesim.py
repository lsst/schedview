import unittest

import healpy as hp
import numpy as np
import pandas as pd

from schedview.compute.comparesim import assign_field_hpids


class TestAssignFieldHpids(unittest.TestCase):

    def setUp(self):
        self.nside = 2**10

        # Pick a few random but reproducible healpix indices.
        rng = np.random.default_rng(42)
        self.sim_hpids = rng.integers(0, hp.nside2npix(self.nside), size=5)
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


if __name__ == "__main__":
    unittest.main()
