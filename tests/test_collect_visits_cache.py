"""Black-box tests for cached_read_visits public API."""

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from schedview.collect.visits import cached_read_visits


class TestCachedReadVisitsAPI(unittest.TestCase):
    """Tests for the public contract of cached_read_visits."""

    def _make_fake_visits(self, day_obs_values=None):
        if day_obs_values is None:
            day_obs_values = [
                20260610,
                20260611,
                20260612,
                20260613,
                20260614,
            ]
        return pd.DataFrame(
            {
                "dayObs": day_obs_values,
                "observationId": range(len(day_obs_values)),
            }
        )

    def _day_obs_mock(self, yyyymmdd):
        m = MagicMock()
        m.yyyymmdd = yyyymmdd
        return m

    def _from_date_side_effect(self, day_obs_value):
        """Return a side_effect callable for DayObs.from_date mocks.

        Parameters
        ----------
        day_obs_value : `int`
            The yyyymmdd value to return for any argument that is not
            ``"today"``.

        Returns
        -------
        side_effect : `callable`
            A function that returns a `~unittest.mock.MagicMock` when
            called with ``"today"`` and a day-obs mock otherwise.
        """

        def side_effect(arg):
            if arg == "today":
                return MagicMock()
            return self._day_obs_mock(day_obs_value)

        return side_effect

    def test_raises_for_non_instrument_source(self):
        with self.assertRaises(ValueError):
            cached_read_visits(20260614, "baseline", cache_dir="/tmp/cache")

    def test_raises_for_opsim_file_source(self):
        with self.assertRaises(ValueError):
            cached_read_visits(20260614, "/path/to/sim.db", cache_dir="/tmp/cache")

    def test_filters_to_requested_day_obs(self):
        """Results contain only visits up to the requested day_obs."""
        fake_visits = self._make_fake_visits()

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch(
                    "schedview.collect.visits._is_cache_fresh",
                    return_value=False,
                ),
                patch(
                    "schedview.collect.visits.read_visits",
                    return_value=fake_visits,
                ),
                patch(
                    "schedview.collect.visits.DayObs.from_date",
                ) as mock_from_date,
            ):
                mock_from_date.side_effect = self._from_date_side_effect(20260612)
                result = cached_read_visits(20260612, "lsstcam", cache_dir=tmpdir)

            self.assertTrue(all(result["dayObs"] <= 20260612))

    def test_warns_when_no_dayobs_column(self):
        """A warning is issued if dayObs column is absent."""
        fake_visits = pd.DataFrame({"observationId": [1, 2, 3]})

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch(
                    "schedview.collect.visits._is_cache_fresh",
                    return_value=False,
                ),
                patch(
                    "schedview.collect.visits.read_visits",
                    return_value=fake_visits,
                ),
                patch(
                    "schedview.collect.visits.DayObs.from_date",
                ) as mock_from_date,
            ):
                mock_from_date.side_effect = self._from_date_side_effect(20260614)
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    result = cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir)

            self.assertEqual(len(result), 3)
            self.assertTrue(any("dayObs" in str(warning.message) for warning in w))

    def test_cache_dir_created_if_absent(self):
        """cache_dir is created automatically when absent."""
        fake_visits = self._make_fake_visits()

        with tempfile.TemporaryDirectory() as tmpdir:
            new_cache_dir = Path(tmpdir) / "new" / "subdir"
            self.assertFalse(new_cache_dir.exists())

            with (
                patch(
                    "schedview.collect.visits._is_cache_fresh",
                    return_value=False,
                ),
                patch(
                    "schedview.collect.visits.read_visits",
                    return_value=fake_visits,
                ),
                patch(
                    "schedview.collect.visits.DayObs.from_date",
                ) as mock_from_date,
            ):
                mock_from_date.side_effect = self._from_date_side_effect(20260614)
                cached_read_visits(20260614, "lsstcam", cache_dir=new_cache_dir)

            self.assertTrue(new_cache_dir.exists())

    def test_second_call_returns_same_data(self):
        """Two calls with same params return equivalent results."""
        from rubin_sim import maf

        fake_visits = self._make_fake_visits()
        stackers = [maf.stackers.DayObsStacker()]

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch(
                    "schedview.collect.visits._is_cache_fresh",
                    return_value=False,
                ),
                patch(
                    "schedview.collect.visits.read_visits",
                    return_value=fake_visits,
                ),
                patch(
                    "schedview.collect.visits.DayObs.from_date",
                ) as mock_from_date,
            ):
                mock_from_date.side_effect = self._from_date_side_effect(20260614)
                result1 = cached_read_visits(
                    20260614,
                    "lsstcam",
                    cache_dir=tmpdir,
                    stackers=stackers,
                )

            # Second call with cache now populated
            with (
                patch(
                    "schedview.collect.visits._is_cache_fresh",
                    return_value=True,
                ),
                patch(
                    "schedview.collect.visits.DayObs.from_date",
                    return_value=self._day_obs_mock(20260614),
                ),
            ):
                result2 = cached_read_visits(
                    20260614,
                    "lsstcam",
                    cache_dir=tmpdir,
                    stackers=stackers,
                )

            pd.testing.assert_frame_equal(result1, result2)


if __name__ == "__main__":
    unittest.main()
