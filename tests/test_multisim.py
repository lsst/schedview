import unittest

import numpy as np
import pandas as pd

import schedview.compute.multisim

NUM_TEST_FIELDS = 5
TEST_RND_SEED = 6563
FIELD_SEQUENCE_IN_SIMS = (
    (0, 1, 2, 2, 2, 3, 4, 4, 4, 4),
    (0, 0, 1, 2, 2, 2, 4, 4),
    (0, 1, 2, 2, 2, 3, 3, 4),
    (0, 1, 2, 3, 4, 2, 2, 4),
)


class TestMultisim(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(seed=TEST_RND_SEED)
        bands = tuple("ugrizy")
        self.fields = pd.DataFrame(
            {
                "fieldId": np.arange(NUM_TEST_FIELDS),
                "fieldRA": rng.uniform(10, 30, NUM_TEST_FIELDS),
                "fieldDec": rng.uniform(-90, -70, NUM_TEST_FIELDS),
                "filter": rng.choice(bands, NUM_TEST_FIELDS),
                "visitExposureTime": 30,
            }
        )

        sim_visits_dfs = []
        for sim_index, this_sim_fields in enumerate(FIELD_SEQUENCE_IN_SIMS):
            sim_nvisits = len(this_sim_fields)
            these_sim_visits = self.fields.loc[this_sim_fields, :].copy()
            these_sim_visits["sim_index"] = sim_index
            these_sim_visits["label"] = f"sim{sim_index}"
            these_sim_visits["start_date"] = (
                pd.to_datetime("2025-09-15T02:00:00Z")
                + pd.to_timedelta(rng.uniform(-10, 10), unit="m")
                + pd.to_timedelta(np.arange(len(these_sim_visits)), unit="m")
                + pd.to_timedelta(rng.uniform(-15, 15, len(these_sim_visits)), unit="s")
            )
            these_sim_visits.sort_values("start_date", inplace=True)
            these_sim_visits.index = pd.Index(np.arange(sim_nvisits), name="observationId")
            sim_visits_dfs.append(these_sim_visits)

        self.visits = pd.concat(sim_visits_dfs)

    def test_often_repeated_fields(self):
        min_counts = 3
        often_repeated_fields, often_repeated_field_stats = schedview.compute.multisim.often_repeated_fields(
            self.visits,
            min_counts=min_counts,
        )
        field_spec_columns = ["fieldRA", "fieldDec", "filter"]
        assert np.all(often_repeated_field_stats.groupby(field_spec_columns)["count"].max() >= min_counts)

        field_ids = self.fields.set_index(field_spec_columns).loc[
            pd.MultiIndex.from_frame(often_repeated_fields), "fieldId"
        ]

        for index_value, row in (
            often_repeated_field_stats.reset_index().set_index(field_spec_columns).iterrows()
        ):
            this_field_sequence = FIELD_SEQUENCE_IN_SIMS[row.sim_index]
            specified_count = this_field_sequence.count(field_ids.loc[index_value])  # type: ignore
            assert row["count"] == specified_count
