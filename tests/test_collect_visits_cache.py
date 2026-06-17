"""Tests for cached_read_visits and _is_cache_fresh."""

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from astropy.time import Time

from schedview import DayObs
from schedview.collect.visits import (
    DDF_STACKERS,
    NIGHT_STACKERS,
    _is_cache_fresh,
    cached_read_visits,
)


def _class_names(stackers):
    """Return the set of fully-qualified class names for a list of stackers."""
    return {type(s).__module__ + "." + type(s).__qualname__ for s in stackers}


class TestIsCacheFresh(unittest.TestCase):
    """Tests for _is_cache_fresh."""

    def test_missing_file_returns_false(self):
        path = Path("/nonexistent/path/visits_lsstcam.h5")
        self.assertFalse(_is_cache_fresh(path))

    def test_fresh_file_returns_true(self):
        """A file whose mtime falls between yesterday's sunrise and today's sunset is fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "visits_lsstcam.h5"
            cache_path.write_bytes(b"fake")

            mock_stat = MagicMock()
            mock_stat.st_mtime = Time.now().unix

            yesterday_dayobs = MagicMock()
            yesterday_dayobs.sunrise = Time("2026-06-16 10:00:00", scale="utc")

            today_dayobs = MagicMock()
            today_dayobs.sunset = Time("2026-06-18 01:00:00", scale="utc")

            with (
                patch("pathlib.Path.stat", return_value=mock_stat),
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    yesterday_dayobs if arg == "yesterday" else today_dayobs
                )
                self.assertTrue(_is_cache_fresh(cache_path))

    def test_stale_file_returns_false(self):
        """A file written before yesterday's sunrise is not fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "visits_lsstcam.h5"
            cache_path.write_bytes(b"fake")

            mock_stat = MagicMock()
            mock_stat.st_mtime = Time.now().unix - 7 * 86400  # a week ago

            yesterday_dayobs = MagicMock()
            yesterday_dayobs.sunrise = Time.now()  # sunrise is "now"; mtime is in the past

            today_dayobs = MagicMock()
            today_dayobs.sunset = Time(Time.now().unix + 3600, format="unix")

            with (
                patch("pathlib.Path.stat", return_value=mock_stat),
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    yesterday_dayobs if arg == "yesterday" else today_dayobs
                )
                self.assertFalse(_is_cache_fresh(cache_path))


class TestCachedReadVisits(unittest.TestCase):
    """Tests for cached_read_visits."""

    def _make_fake_visits(self, day_obs_values=None):
        if day_obs_values is None:
            day_obs_values = [20260610, 20260611, 20260612, 20260613, 20260614]
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

    def test_raises_for_non_instrument_source(self):
        with self.assertRaises(ValueError):
            cached_read_visits(20260614, "baseline", cache_dir="/tmp/cache")

    def test_raises_for_opsim_file_source(self):
        with self.assertRaises(ValueError):
            cached_read_visits(20260614, "/path/to/sim.db", cache_dir="/tmp/cache")

    def test_cache_miss_calls_read_visits_and_writes_cache(self):
        """On a cache miss, read_visits is called and both HDF5 keys are written."""
        from rubin_sim import maf

        fake_visits = self._make_fake_visits()
        stackers = [maf.stackers.DayObsStacker()]

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_visits", return_value=fake_visits) as mock_rv,
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260612)
                )
                result = cached_read_visits(20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers)

            mock_rv.assert_called_once()

            cache_path = Path(tmpdir) / "visits_lsstcam.h5"
            self.assertTrue(cache_path.exists())
            stored_visits = pd.read_hdf(str(cache_path), key="visits")
            stored_stackers = pd.read_hdf(str(cache_path), key="stackers")
            self.assertEqual(len(stored_visits), len(fake_visits))
            self.assertIn("class_name", stored_stackers.columns)
            self.assertTrue(all(result["dayObs"] <= 20260612))

    def test_cache_hit_does_not_call_read_visits(self):
        """On a valid cache hit (fresh + matching stackers), read_visits is not called."""
        from rubin_sim import maf

        fake_visits = self._make_fake_visits()
        stackers = [maf.stackers.DayObsStacker()]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "visits_lsstcam.h5"
            fake_visits.to_hdf(str(cache_path), key="visits")
            pd.DataFrame({"class_name": sorted(_class_names(stackers))}).to_hdf(
                str(cache_path), key="stackers", append=True
            )

            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=True),
                patch("schedview.collect.visits.read_visits") as mock_rv,
                patch("schedview.collect.visits.DayObs.from_date",
                      return_value=self._day_obs_mock(20260612)),
            ):
                result = cached_read_visits(20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers)

            mock_rv.assert_not_called()
            self.assertTrue(all(result["dayObs"] <= 20260612))

    def test_stacker_mismatch_regenerates_cache(self):
        """A fresh cache built with different stackers is regenerated."""
        from rubin_sim import maf

        fake_visits = self._make_fake_visits()
        stackers_in_cache = [maf.stackers.DayObsStacker()]
        stackers_requested = [maf.stackers.DayObsStacker(), maf.stackers.DayObsISOStacker()]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "visits_lsstcam.h5"
            fake_visits.to_hdf(str(cache_path), key="visits")
            pd.DataFrame({"class_name": sorted(_class_names(stackers_in_cache))}).to_hdf(
                str(cache_path), key="stackers", append=True
            )

            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=True),
                patch("schedview.collect.visits.read_visits", return_value=fake_visits) as mock_rv,
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir, stackers=stackers_requested)

            mock_rv.assert_called_once()
            new_names = set(pd.read_hdf(str(cache_path), key="stackers")["class_name"])
            self.assertEqual(new_names, _class_names(stackers_requested))

    def test_ddf_uses_ddf_suffix_in_filename(self):
        """DDF cache files use the _ddf suffix and read_ddf_visits is called."""
        fake_visits = self._make_fake_visits()

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_ddf_visits", return_value=fake_visits),
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir, ddf=True)

            self.assertTrue((Path(tmpdir) / "visits_lsstcam_ddf.h5").exists())
            self.assertFalse((Path(tmpdir) / "visits_lsstcam.h5").exists())

    def test_default_stackers_non_ddf(self):
        """When stackers=None and ddf=False, NIGHT_STACKERS are used."""
        fake_visits = self._make_fake_visits()

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_visits", return_value=fake_visits) as mock_rv,
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir, stackers=None)

            _, call_kwargs = mock_rv.call_args
            self.assertEqual(_class_names(call_kwargs["stackers"]), _class_names(NIGHT_STACKERS))

    def test_default_stackers_ddf(self):
        """When stackers=None and ddf=True, DDF_STACKERS + DayObsStacker are used."""
        from rubin_sim import maf

        fake_visits = self._make_fake_visits()
        expected = _class_names(DDF_STACKERS + [maf.stackers.DayObsStacker()])

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_ddf_visits", return_value=fake_visits) as mock_rdv,
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir, stackers=None, ddf=True)

            _, call_kwargs = mock_rdv.call_args
            self.assertEqual(_class_names(call_kwargs["stackers"]), expected)

    def test_cache_dir_created_if_absent(self):
        """cache_dir is created automatically when it does not exist."""
        fake_visits = self._make_fake_visits()

        with tempfile.TemporaryDirectory() as tmpdir:
            new_cache_dir = Path(tmpdir) / "new" / "subdir"
            self.assertFalse(new_cache_dir.exists())

            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_visits", return_value=fake_visits),
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                cached_read_visits(20260614, "lsstcam", cache_dir=new_cache_dir)

            self.assertTrue(new_cache_dir.exists())

    def test_warns_when_no_dayobs_column(self):
        """A warning is issued and unfiltered data returned if dayObs column is absent."""
        fake_visits = pd.DataFrame({"observationId": [1, 2, 3]})

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("schedview.collect.visits._is_cache_fresh", return_value=False),
                patch("schedview.collect.visits.read_visits", return_value=fake_visits),
                patch("schedview.collect.visits.DayObs.from_date") as mock_from_date,
            ):
                mock_from_date.side_effect = lambda arg: (
                    MagicMock() if arg == "today" else self._day_obs_mock(20260614)
                )
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    result = cached_read_visits(20260614, "lsstcam", cache_dir=tmpdir)

            self.assertEqual(len(result), 3)
            self.assertTrue(any("dayObs" in str(warning.message) for warning in w))


if __name__ == "__main__":
    unittest.main()
