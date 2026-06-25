"""Tests for schedview.compute.smallsum module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.site_models import Almanac

from schedview.compute.smallsum import (
    _build_night_hours,
    _unique_targets,
    _visits_summary,
    compute_smallsum,
    compute_tinysum,
)

SCIENCE_PROGRAMS = ("BLOCK-365", "BLOCK-407")
ALL_BANDS: tuple[str, ...] = tuple(ModelObservatory(no_sky=True).bandlist)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_visits() -> pd.DataFrame:
    """Create a sample visits DataFrame spanning two nights."""
    rng = np.random.default_rng(42)
    n_night1 = 50
    n_night2 = 30
    n_total = n_night1 + n_night2

    dayobs = np.array([20250601] * n_night1 + [20250602] * n_night2)
    bands = rng.choice(ALL_BANDS, size=n_total)
    science_programs = rng.choice(
        [*SCIENCE_PROGRAMS, "ENG-001", "CALIB-002"],
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

    return pd.DataFrame(
        {
            "dayObs": dayobs,
            "observationId": np.arange(n_total),
            "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n_total),
            "eff_time_median": rng.uniform(20.0, 40.0, size=n_total),
            "exp_time": rng.uniform(25.0, 35.0, size=n_total),
            "band": bands,
            "science_program": science_programs,
            "target_name": target_names,
            "observation_reason": observation_reasons,
            "start_timestamp": start_timestamps,
            "airmass": rng.uniform(1.0, 2.5, size=n_total),
            "HA": rng.uniform(-4.0, 4.0, size=n_total),
        }
    )


@pytest.fixture
def almanac() -> Almanac:
    """Create a shared Almanac instance."""
    return Almanac()


# ---------------------------------------------------------------------------
# Tests for _unique_targets helper
# ---------------------------------------------------------------------------


class TestUniqueTargets:
    @pytest.mark.parametrize(
        ("values", "expected_in", "expected_out"),
        [
            (["COSMOS", "XMM-LSS", "ELAIS"], ["COSMOS", "XMM-LSS", "ELAIS"], []),
            (["ddf_COSMOS", "DDF XMM-LSS"], ["COSMOS", "XMM-LSS"], ["ddf_", "DDF "]),
            (["ELAIS, XMM-LSS"], ["ELAIS", "XMM-LSS"], []),
        ],
    )
    def test_content(self, values, expected_in, expected_out):
        result = _unique_targets(pd.Series(values))
        for item in expected_in:
            assert item in result
        for item in expected_out:
            assert item not in result

    def test_deduplication(self):
        result = _unique_targets(pd.Series(["COSMOS", "COSMOS", "ddf_COSMOS"]))
        assert result.count("COSMOS") == 1

    @pytest.mark.parametrize(
        ("values", "expected"),
        [
            (["", "", "COSMOS"], "COSMOS"),
            ([np.nan, None, "COSMOS"], "COSMOS"),
            (["", ""], ""),
        ],
    )
    def test_empty_nan_handling(self, values, expected):
        assert _unique_targets(pd.Series(values)) == expected


# ---------------------------------------------------------------------------
# Tests for _visits_summary helper
# ---------------------------------------------------------------------------


class TestVisitsSummary:
    def test_basic_output(self, sample_visits):
        result = _visits_summary(sample_visits.iloc[:10])
        assert result["visits"] == 10
        assert {
            "first",
            "last",
            "teff_total",
            "teff_q1",
            "teff_median",
            "teff_q3",
            "fwhm_median",
            "airmass_median",
            "HA_median",
        }.issubset(set(result.index))

    def test_teff_total_equals_mean_times_count(self, sample_visits):
        group = sample_visits.iloc[:20]
        result = _visits_summary(group)
        assert np.isclose(result["teff_total"], group["eff_time_median"].mean() * len(group))

    def test_single_visit(self, sample_visits):
        result = _visits_summary(sample_visits.iloc[:1])
        assert result["visits"] == 1
        assert result["first"] == result["last"]


# ---------------------------------------------------------------------------
# Tests for compute_tinysum
# ---------------------------------------------------------------------------


class TestComputeTinysum:
    def test_one_row_per_night(self, sample_visits):
        result = compute_tinysum(sample_visits)
        assert len(result) == 2
        assert {20250601, 20250602}.issubset(set(result.index))

    def test_total_column(self, sample_visits):
        result = compute_tinysum(sample_visits)
        assert result.loc[20250601, "Total"] == 50
        assert result.loc[20250602, "Total"] == 30

    def test_band_counts_sum_to_total(self, sample_visits):
        result = compute_tinysum(sample_visits)
        band_cols = [f"# {b}" for b in ALL_BANDS]
        for day in result.index:
            assert result.loc[day, band_cols].sum() == result.loc[day, "Total"]

    def test_band_and_science_counts_are_int(self, sample_visits):
        result = compute_tinysum(sample_visits)
        for b in ALL_BANDS:
            assert pd.api.types.is_integer_dtype(result[f"# {b}"])
        assert pd.api.types.is_integer_dtype(result["science"])

    def test_science_count_correct(self, sample_visits):
        result = compute_tinysum(sample_visits, science_programs=SCIENCE_PROGRAMS)
        for day in result.index:
            expected = len(
                sample_visits[
                    (sample_visits["dayObs"] == day)
                    & (sample_visits["science_program"].isin(SCIENCE_PROGRAMS))
                ]
            )
            assert result.loc[day, "science"] == expected

    def test_teff_stats_reasonable(self, sample_visits):
        result = compute_tinysum(sample_visits)
        for day in result.index:
            assert (
                result.loc[day, "q1 eff_time"]
                <= result.loc[day, "median eff_time"]
                <= result.loc[day, "q3 eff_time"]
            )

    def test_mean_eff_time_over_exp_time(self, sample_visits):
        result = compute_tinysum(sample_visits)
        for day in result.index:
            day_visits = sample_visits[sample_visits["dayObs"] == day]
            expected = day_visits["eff_time_median"].sum() / day_visits["exp_time"].sum()
            assert np.isclose(result.loc[day, "total eff_time/exp_time"], expected)

    def test_no_almanac_omits_rate_columns(self, sample_visits):
        result = compute_tinysum(sample_visits, almanac=None)
        assert {"night_hours", "visits/hour", "teff/minute"}.isdisjoint(result.columns)

    def test_with_almanac_adds_rate_columns(self, sample_visits, almanac):
        result = compute_tinysum(sample_visits, almanac=almanac)
        assert {"night_hours", "visits/hour", "teff/minute"}.issubset(result.columns)
        assert (result["night_hours"].dropna() > 0).all()

    def test_no_science_visits_night(self):
        visits = pd.DataFrame(
            {
                "dayObs": [20250601] * 5,
                "observationId": range(5),
                "seeingFwhmGeom": [1.0] * 5,
                "eff_time_median": [30.0] * 5,
                "exp_time": [30.0] * 5,
                "band": list("grriz"),
                "science_program": ["ENG-001"] * 5,
                "target_name": ["test"] * 5,
            }
        )
        result = compute_tinysum(visits, science_programs=("BLOCK-365",))
        assert result.loc[20250601, "science"] == 0
        assert result.loc[20250601, "science targets"] == ""

    def test_missing_bands(self):
        visits = pd.DataFrame(
            {
                "dayObs": [20250601] * 3,
                "observationId": range(3),
                "seeingFwhmGeom": [1.0] * 3,
                "eff_time_median": [30.0] * 3,
                "exp_time": [30.0] * 3,
                "band": ["g", "r", "i"],
                "science_program": ["BLOCK-365"] * 3,
                "target_name": ["COSMOS"] * 3,
            }
        )
        result = compute_tinysum(visits, science_programs=("BLOCK-365",))
        assert result.loc[20250601, "# g"] == 1
        for b in ("u", "z", "y"):
            assert result.loc[20250601, f"# {b}"] == 0


# ---------------------------------------------------------------------------
# Tests for compute_smallsum
# ---------------------------------------------------------------------------


class TestComputeSmallsum:
    def test_index_levels(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert result.index.names == ["dayObs", "subset"]

    def test_all_subset_present(self, sample_visits):
        result = compute_smallsum(sample_visits)
        for day in (20250601, 20250602):
            assert "all" in result.loc[day].index.get_level_values("subset")

    def test_all_visits_count(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert result.loc[(20250601, "all"), "visits"] == 50
        assert result.loc[(20250602, "all"), "visits"] == 30

    def test_band_subsets_present_and_sum(self, sample_visits):
        result = compute_smallsum(sample_visits)
        all_subsets = result.index.get_level_values("subset").unique()
        bands_present = [b for b in ALL_BANDS if b in all_subsets]
        assert bands_present
        for day in (20250601, 20250602):
            day_data = result.loc[day]
            day_bands = [b for b in ALL_BANDS if b in day_data.index.get_level_values("subset")]
            assert sum(day_data.loc[b, "visits"] for b in day_bands) == day_data.loc["all", "visits"]

    def test_science_subsets_present_and_sum(self, sample_visits):
        result = compute_smallsum(sample_visits, science_programs=SCIENCE_PROGRAMS)
        all_subsets = result.index.get_level_values("subset").unique()
        assert {"science", "not_science"}.issubset(all_subsets)
        for day in (20250601, 20250602):
            day_data = result.loc[day]
            if {"science", "not_science"}.issubset(day_data.index):
                assert (
                    day_data.loc["science", "visits"] + day_data.loc["not_science", "visits"]
                    == day_data.loc["all", "visits"]
                )

    def test_observation_reason_subsets(self, sample_visits):
        result = compute_smallsum(sample_visits)
        all_subsets = result.index.get_level_values("subset").unique()
        assert any(r in all_subsets for r in ("survey", "calibration", "engineering"))

    def test_target_name_subsets(self, sample_visits):
        result = compute_smallsum(sample_visits)
        all_subsets = result.index.get_level_values("subset").unique()
        assert any(t in all_subsets for t in ("COSMOS", "XMM-LSS", "ELAIS"))

    def test_empty_target_becomes_no_target_name(self):
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
        assert "no target name" in result.loc[20250601].index.get_level_values("subset")

    def test_output_columns(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert set(result.columns) == {
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

    def test_teff_quartile_ordering(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert (result["teff_q1"] <= result["teff_median"]).all()
        assert (result["teff_median"] <= result["teff_q3"]).all()

    def test_first_before_last(self, sample_visits):
        result = compute_smallsum(sample_visits)
        assert (result["first"] <= result["last"]).all()

    def test_subset_order_matches_contract(self, sample_visits):
        result = compute_smallsum(sample_visits, science_programs=SCIENCE_PROGRAMS)
        day = result.index.get_level_values("dayObs")[0]
        subsets = list(result.loc[day].index)

        assert subsets[0] == "all"

        first_band_pos = min(subsets.index(b) for b in ALL_BANDS if b in subsets)
        first_science_pos = min(subsets.index(s) for s in ("science", "not_science") if s in subsets)

        assert first_band_pos < first_science_pos


# ---------------------------------------------------------------------------
# Tests for _build_night_hours helper
# ---------------------------------------------------------------------------


class TestBuildNightHours:
    def test_returns_series(self, almanac):
        index = pd.Index([20250601, 20250602])
        result = _build_night_hours(almanac, index)
        assert isinstance(result, pd.Series)
        assert len(result) == len(index)

    def test_positive_hours(self, almanac):
        result = _build_night_hours(almanac, pd.Index([20250601, 20250602]))
        for val in result.dropna():
            assert 4.0 < val < 12.0
