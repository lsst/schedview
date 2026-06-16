"""Tests for schedview.compute.smallsum module."""

import numpy as np
import pandas as pd
import pytest
from rubin_scheduler.site_models import Almanac

from schedview.compute.smallsum import (
    _build_night_hours,
    _unique_targets,
    _visits_summary,
    compute_smallsum,
    compute_tinysum,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_visits():
    """Create a sample visits DataFrame spanning two nights."""
    rng = np.random.default_rng(42)
    n_night1 = 50
    n_night2 = 30
    n_total = n_night1 + n_night2

    dayobs = np.array([20250601] * n_night1 + [20250602] * n_night2)
    bands = rng.choice(list("ugrizy"), size=n_total)
    science_programs = rng.choice(
        ["BLOCK-365", "BLOCK-407", "ENG-001", "CALIB-002"],
        size=n_total,
    )
    target_names = rng.choice(
        ["COSMOS", "XMM-LSS", "ddf_COSMOS", "ELAIS, XMM-LSS", ""],
        size=n_total,
    )
    observation_reasons = rng.choice(
        ["survey", "calibration", "engineering"],
        size=n_total,
    )

    # Timestamps: night 1 starts at MJD 60827, night 2 at MJD 60828
    base_timestamps_n1 = 60827.0 * 86400 + np.linspace(0, 8 * 3600, n_night1)
    base_timestamps_n2 = 60828.0 * 86400 + np.linspace(0, 7 * 3600, n_night2)
    start_timestamps = np.concatenate([base_timestamps_n1, base_timestamps_n2])

    visits = pd.DataFrame(
        {
            "dayObs": dayobs,
            "observationId": np.arange(n_total),
            "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n_total),
            "eff_time_median": rng.uniform(20.0, 40.0, size=n_total),
            "band": bands,
            "science_program": science_programs,
            "target_name": target_names,
            "observation_reason": observation_reasons,
            "start_timestamp": start_timestamps,
            "airmass": rng.uniform(1.0, 2.5, size=n_total),
            "HA": rng.uniform(-4.0, 4.0, size=n_total),
        }
    )
    return visits


@pytest.fixture
def almanac():
    """Create a shared Almanac instance."""
    return Almanac()


# ---------------------------------------------------------------------------
# Tests for _unique_targets helper
# ---------------------------------------------------------------------------


class TestUniqueTargets:
    def test_basic(self):
        series = pd.Series(["COSMOS", "XMM-LSS", "ELAIS"])
        result = _unique_targets(series)
        assert "COSMOS" in result
        assert "XMM-LSS" in result
        assert "ELAIS" in result

    def test_strips_ddf_prefix(self):
        series = pd.Series(["ddf_COSMOS", "DDF XMM-LSS"])
        result = _unique_targets(series)
        assert "COSMOS" in result
        assert "XMM-LSS" in result
        assert "ddf_" not in result
        assert "DDF " not in result

    def test_splits_multi_target(self):
        series = pd.Series(["ELAIS, XMM-LSS"])
        result = _unique_targets(series)
        assert "ELAIS" in result
        assert "XMM-LSS" in result

    def test_deduplication(self):
        series = pd.Series(["COSMOS", "COSMOS", "ddf_COSMOS"])
        result = _unique_targets(series)
        # Should only appear once
        assert result.count("COSMOS") == 1

    def test_empty_strings_ignored(self):
        series = pd.Series(["", "", "COSMOS"])
        result = _unique_targets(series)
        assert result == "COSMOS"

    def test_nan_handled(self):
        series = pd.Series([np.nan, None, "COSMOS"])
        result = _unique_targets(series)
        assert result == "COSMOS"

    def test_all_empty(self):
        series = pd.Series(["", ""])
        result = _unique_targets(series)
        assert result == ""


# ---------------------------------------------------------------------------
# Tests for _visits_summary helper
# ---------------------------------------------------------------------------


class TestVisitsSummary:
    def test_basic_output(self, sample_visits):
        group = sample_visits.iloc[:10]
        result = _visits_summary(group)
        assert result["visits"] == 10
        assert "first" in result.index
        assert "last" in result.index
        assert "teff_total" in result.index
        assert "teff_q1" in result.index
        assert "teff_median" in result.index
        assert "teff_q3" in result.index
        assert "fwhm_median" in result.index
        assert "airmass_median" in result.index
        assert "HA_median" in result.index

    def test_teff_total_equals_mean_times_count(self, sample_visits):
        group = sample_visits.iloc[:20]
        result = _visits_summary(group)
        expected_total = group["eff_time_median"].mean() * 20
        assert np.isclose(result["teff_total"], expected_total)

    def test_single_visit(self, sample_visits):
        group = sample_visits.iloc[:1]
        result = _visits_summary(group)
        assert result["visits"] == 1
        assert result["first"] == result["last"]


# ---------------------------------------------------------------------------
# Tests for compute_tinysum
# ---------------------------------------------------------------------------


class TestComputeTinysum:
    def test_one_row_per_night(self, sample_visits):
        result = compute_tinysum(sample_visits)
        assert len(result) == 2  # Two nights
        assert 20250601 in result.index
        assert 20250602 in result.index

    def test_total_column(self, sample_visits):
        result = compute_tinysum(sample_visits)
        assert result.loc[20250601, "Total"] == 50
        assert result.loc[20250602, "Total"] == 30

    def test_band_counts_sum_to_total(self, sample_visits):
        result = compute_tinysum(sample_visits)
        band_cols = [f"# {b}" for b in "ugrizy"]
        for day in result.index:
            assert result.loc[day, band_cols].sum() == result.loc[day, "Total"]

    def test_band_counts_are_int(self, sample_visits):
        result = compute_tinysum(sample_visits)
        for b in "ugrizy":
            assert result[f"# {b}"].dtype == int

    def test_science_count_is_int(self, sample_visits):
        result = compute_tinysum(sample_visits)
        assert result["# science"].dtype == int

    def test_science_count_correct(self, sample_visits):
        science_progs = ("BLOCK-365", "BLOCK-407")
        result = compute_tinysum(sample_visits, science_programs=science_progs)
        for day in result.index:
            expected = len(
                sample_visits[
                    (sample_visits["dayObs"] == day)
                    & (sample_visits["science_program"].isin(science_progs))
                ]
            )
            assert result.loc[day, "# science"] == expected

    def test_teff_stats_reasonable(self, sample_visits):
        result = compute_tinysum(sample_visits)
        # q1 <= median <= q3
        for day in result.index:
            assert result.loc[day, "teff_q1"] <= result.loc[day, "teff_median"]
            assert result.loc[day, "teff_median"] <= result.loc[day, "teff_q3"]

    def test_no_almanac_omits_rate_columns(self, sample_visits):
        result = compute_tinysum(sample_visits, almanac=None)
        assert "night_hours" not in result.columns
        assert "visits/hour" not in result.columns
        assert "teff/minute" not in result.columns

    def test_with_almanac_adds_rate_columns(self, sample_visits, almanac):
        result = compute_tinysum(sample_visits, almanac=almanac)
        assert "night_hours" in result.columns
        assert "visits/hour" in result.columns
        assert "teff/minute" in result.columns
        # Night hours should be positive
        assert (result["night_hours"].dropna() > 0).all()

    def test_no_science_visits_night(self):
        """A night with no science visits should have 0 count and empty targets."""
        visits = pd.DataFrame(
            {
                "dayObs": [20250601] * 5,
                "observationId": range(5),
                "seeingFwhmGeom": [1.0] * 5,
                "eff_time_median": [30.0] * 5,
                "band": list("grriz"),
                "science_program": ["ENG-001"] * 5,
                "target_name": ["test"] * 5,
            }
        )
        result = compute_tinysum(visits, science_programs=("BLOCK-365",))
        assert result.loc[20250601, "# science"] == 0
        assert result.loc[20250601, "science targets"] == ""

    def test_missing_bands(self):
        """Nights missing some bands should have 0 for those bands."""
        visits = pd.DataFrame(
            {
                "dayObs": [20250601] * 3,
                "observationId": range(3),
                "seeingFwhmGeom": [1.0] * 3,
                "eff_time_median": [30.0] * 3,
                "band": ["g", "r", "i"],
                "science_program": ["BLOCK-365"] * 3,
                "target_name": ["COSMOS"] * 3,
            }
        )
        result = compute_tinysum(visits, science_programs=("BLOCK-365",))
        assert result.loc[20250601, "# u"] == 0
        assert result.loc[20250601, "# z"] == 0
        assert result.loc[20250601, "# y"] == 0
        assert result.loc[20250601, "# g"] == 1


# ---------------------------------------------------------------------------
# Tests for compute_smallsum
# ---------------------------------------------------------------------------


class TestComputeSmallsum:
    def test_index_levels(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert result.index.names == ["dayObs", "subset"]

    def test_all_subset_present(self, sample_visits):
        result = compute_smallsum(sample_visits)
        for day in [20250601, 20250602]:
            day_subsets = result.loc[day].index.get_level_values("subset")
            assert "all" in day_subsets

    def test_all_visits_count(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert result.loc[(20250601, "all"), "visits"] == 50
        assert result.loc[(20250602, "all"), "visits"] == 30

    def test_band_subsets_present(self, sample_visits):
        result = compute_smallsum(sample_visits)
        # Check that at least some band subsets exist
        all_subsets = result.index.get_level_values("subset").unique()
        bands_present = [b for b in "ugrizy" if b in all_subsets]
        assert len(bands_present) > 0

    def test_band_subset_counts_sum(self, sample_visits):
        result = compute_smallsum(sample_visits)
        for day in [20250601, 20250602]:
            day_data = result.loc[day]
            band_subsets = [b for b in "ugrizy" if b in day_data.index.get_level_values("subset")]
            band_total = sum(day_data.loc[b, "visits"] for b in band_subsets)
            all_total = day_data.loc["all", "visits"]
            assert band_total == all_total

    def test_science_subsets_present(self, sample_visits):
        result = compute_smallsum(
            sample_visits, science_programs=("BLOCK-365", "BLOCK-407")
        )
        all_subsets = result.index.get_level_values("subset").unique()
        assert "science" in all_subsets
        assert "not_science" in all_subsets

    def test_science_counts_sum(self, sample_visits):
        science_progs = ("BLOCK-365", "BLOCK-407")
        result = compute_smallsum(sample_visits, science_programs=science_progs)
        for day in [20250601, 20250602]:
            day_data = result.loc[day]
            if "science" in day_data.index and "not_science" in day_data.index:
                sci = day_data.loc["science", "visits"]
                not_sci = day_data.loc["not_science", "visits"]
                total = day_data.loc["all", "visits"]
                assert sci + not_sci == total

    def test_observation_reason_subsets(self, sample_visits):
        result = compute_smallsum(sample_visits)
        all_subsets = result.index.get_level_values("subset").unique()
        # At least one observation reason from sample data
        assert any(
            r in all_subsets for r in ["survey", "calibration", "engineering"]
        )

    def test_target_name_subsets(self, sample_visits):
        result = compute_smallsum(sample_visits)
        all_subsets = result.index.get_level_values("subset").unique()
        # At least one target from sample data
        assert any(t in all_subsets for t in ["COSMOS", "XMM-LSS", "ELAIS"])

    def test_empty_target_becomes_no_target_name(self):
        """Visits with empty target_name should appear under 'no target name'."""
        visits = pd.DataFrame(
            {
                "dayObs": [20250601] * 3,
                "observationId": range(3),
                "seeingFwhmGeom": [1.0] * 3,
                "eff_time_median": [30.0] * 3,
                "band": ["g", "r", "i"],
                "science_program": ["ENG-001"] * 3,
                "target_name": ["", "", ""],
                "observation_reason": ["survey"] * 3,
                "start_timestamp": [1.0, 2.0, 3.0],
                "airmass": [1.2, 1.3, 1.4],
                "HA": [0.1, 0.2, 0.3],
            }
        )
        result = compute_smallsum(visits, science_programs=("BLOCK-365",))
        all_subsets = result.loc[20250601].index.get_level_values("subset")
        assert "no target name" in all_subsets

    def test_output_columns(self, sample_visits):
        result = compute_smallsum(sample_visits)
        expected_cols = {
            "visits",
            "first",
            "last",
            "teff_total",
            "teff_q1",
            "teff_median",
            "teff_q3",
            "fwhm_median",
            "airmass_median",
            "HA_median",
        }
        assert expected_cols == set(result.columns)

    def test_teff_quartile_ordering(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert (result["teff_q1"] <= result["teff_median"]).all()
        assert (result["teff_median"] <= result["teff_q3"]).all()

    def test_first_before_last(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert (result["first"] <= result["last"]).all()


# ---------------------------------------------------------------------------
# Tests for _build_night_hours helper
# ---------------------------------------------------------------------------


class TestBuildNightHours:
    def test_returns_series(self, almanac):
        index = pd.Index([20250601, 20250602])
        result = _build_night_hours(almanac, index)
        assert isinstance(result, pd.Series)
        assert len(result) == 2

    def test_positive_hours(self, almanac):
        index = pd.Index([20250601, 20250602])
        result = _build_night_hours(almanac, index)
        # Night hours should be positive and reasonable (4-12 hours)
        for val in result.dropna():
            assert 4.0 < val < 12.0
