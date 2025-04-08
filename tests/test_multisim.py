import unittest

import bokeh.models
import numpy as np
import pandas as pd

import schedview.compute.multisim
import schedview.plot.multisim

NUM_TEST_FIELDS = 5
TEST_RND_SEED = 6563
FIELD_SEQUENCE_IN_SIMS = (
    (0, 1, 2, 2, 2, 3, 4, 4, 4, 4),
    (0, 0, 1, 2, 2, 2, 4, 4),
    (0, 1, 2, 2, 2, 3, 3, 4),
    (0, 1, 2, 3, 4, 2, 2, 4),
    (0, 1, 3, 4, 4),
    (0, 1, 4, 4, 4),
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
                "band": rng.choice(bands, NUM_TEST_FIELDS),
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
        field_spec_columns = ["fieldRA", "fieldDec", "band"]
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

    def test_count_visits_by_sim(self):
        visit_spec_columns = ("fieldRA", "fieldDec", "band", "visitExposureTime")
        counts_df = schedview.compute.multisim.count_visits_by_sim(
            self.visits, visit_spec_columns=visit_spec_columns
        )
        for field_id, field_row in self.fields.loc[:, list(visit_spec_columns)].iterrows():
            for sim_id, field_sequence in enumerate(FIELD_SEQUENCE_IN_SIMS):
                assert counts_df.loc[tuple(field_row), sim_id] == field_sequence.count(field_id)

    def test_common_fraction(self):
        visit_counts = schedview.compute.multisim.count_visits_by_sim(self.visits)
        for sim1, field_tuple1 in enumerate(FIELD_SEQUENCE_IN_SIMS):
            for sim2, field_tuple2 in enumerate(FIELD_SEQUENCE_IN_SIMS):
                for match_count in True, False:

                    if match_count:
                        field_list2 = list(field_tuple2)
                        common_field_count = 0
                        for field in field_tuple1:
                            field_matched = field in field_list2
                            if field_matched:
                                common_field_count += 1
                                field_list2.remove(field)
                    else:
                        common_field_count = len([f for f in field_tuple2 if f in field_tuple1])

                    expected_common_fraction = float(common_field_count) / len(field_tuple2)
                    test_common_fraction = schedview.compute.multisim.fraction_common(
                        visit_counts, sim1, sim2, match_count=match_count
                    )
                    assert test_common_fraction == expected_common_fraction

    def test_make_fraction_common_matrix(self):
        visit_counts = schedview.compute.multisim.count_visits_by_sim(self.visits)
        common_fraction_matrix = schedview.compute.multisim.make_fraction_common_matrix(visit_counts)
        common_fraction_matrix_unmatched = schedview.compute.multisim.make_fraction_common_matrix(
            visit_counts, match_count=False
        )
        for sim1 in range(len(FIELD_SEQUENCE_IN_SIMS)):
            for sim2 in range(len(FIELD_SEQUENCE_IN_SIMS)):
                matched_common_fraction = common_fraction_matrix.loc[sim1, sim2]
                assert matched_common_fraction == schedview.compute.multisim.fraction_common(
                    visit_counts, sim1, sim2
                )
                unmatched_common_fraction = common_fraction_matrix_unmatched.loc[sim1, sim2]
                assert unmatched_common_fraction == schedview.compute.multisim.fraction_common(
                    visit_counts, sim1, sim2, match_count=False
                )

    def test_match_visits_across_sims(self):
        start_times = self.visits.set_index(["fieldId", "sim_index"])["start_date"]
        matched_visits = schedview.compute.multisim.match_visits_across_sims(
            start_times.loc[4, :], sim_indexes=(0, 1)
        )
        # Hand checked values for these test data.
        assert matched_visits is not None
        assert np.isclose(matched_visits.loc[:, "delta"], [-573.278053, -604.849867]).all()

        # What if there are no matches?
        matched_visits = schedview.compute.multisim.match_visits_across_sims(
            start_times.loc[2, :], sim_indexes=(0, 4)
        )
        assert len(matched_visits) == 0

        # What about no visits in either sim?
        matched_visits = schedview.compute.multisim.match_visits_across_sims(
            start_times.loc[2, :], sim_indexes=(4, 5)
        )
        assert len(matched_visits) == 0

    def test_compute_matched_visit_delta_statistics(self):
        matched_visit_stats = schedview.compute.multisim.compute_matched_visit_delta_statistics(self.visits)
        assert tuple(matched_visit_stats.index.names) == (
            "fieldRA",
            "fieldDec",
            "band",
            "visitExposureTime",
            "sim_index",
        )
        assert tuple(matched_visit_stats.columns) == (
            "count",
            "mean",
            "std",
            "min",
            "25%",
            "50%",
            "75%",
            "max",
        )

    def test_generate_sim_indicators(self):
        sim_labels = ["hen", "ducks", "geese", "oysters"]
        indicators = schedview.plot.multisim.generate_sim_indicators(sim_labels)
        assert isinstance(indicators.color_mapper, bokeh.models.CategoricalColorMapper)
        assert isinstance(indicators.color_dict, dict)
        assert isinstance(indicators.marker_mapper, bokeh.models.CategoricalMarkerMapper)
        assert isinstance(indicators.hatch_dict, dict)

    def test_plot_airmass_vs_time(self):
        fig = schedview.plot.multisim.plot_alt_airmass_vs_time(bokeh.models.ColumnDataSource(self.visits))
        self.assertIsInstance(fig, bokeh.models.layouts.LayoutDOM)

    def test_overplot_kernel_density_estimates(self):
        fig = schedview.plot.multisim.overplot_kernel_density_estimates(
            self.visits, "fieldDec", np.arange(-90, 90, 1), 0.1
        )
        self.assertIsInstance(fig, bokeh.models.layouts.LayoutDOM)
