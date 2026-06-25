import os
import unittest
from unittest import mock

import pandas as pd

from schedview.collect import get_observatory_status_summary

# Set TEST_WITH_EFD=T (or TRUE/1) to run the test against the live EFD web
# service. It is skipped by default so automated CI does not need EFD access.
USE_EFD = os.environ.get("TEST_WITH_EFD", "F").upper() in ("T", "TRUE", "1")


class TestGetObservatoryStatusSummary(unittest.TestCase):
    test_day_obs = 20260604
    test_day_obs_max = 20260605

    def test_get_observatory_status_summary_mocked(self):
        """Unit test with the EFD web service fully mocked out."""

        # The summary that count_observatory_states would return: one row per
        # night, indexed by day_obs, with a breakdown of downtime hours.
        expected_summary = pd.DataFrame(
            {
                "sunset12": pd.to_datetime(["2026-06-04 22:45:42.147656"]),
                "sunrise12": pd.to_datetime(["2026-06-05 10:37:19.272813"]),
                "night_hours": [11.860312543809414],
                "weather_down": [1.9343212781941594],
                "downtime_down": [0.0],
                "fault_down": [0.03295169055555558],
                "operational_hours": [9.893039575059698],
                "idle_down": [1.9343212781941594],
                "unknown_down": [0.0],
            },
            index=pd.Index([20260604], name="day_obs"),
        )
        # get_observatory_state_times returns a table of state intervals, one
        # row per (night, state) with start/end times and duration in hours.
        # count_observatory_states is also mocked, so these contents only need
        # to be shape-realistic.
        fake_state_times = pd.DataFrame(
            {
                "day_obs": [20260604, 20260604, 20260604, 20260604],
                "sunset12": pd.to_datetime(["2026-06-04 22:45:42.147656"] * 4),
                "sunrise12": pd.to_datetime(["2026-06-05 10:37:19.272813"] * 4),
                "start": pd.to_datetime(
                    [
                        "2026-06-04 22:45:42.147656",
                        "2026-06-05 08:39:17.090126",
                        "2026-06-05 08:41:15.716212",
                        "2026-06-05 08:41:15.716212",
                    ]
                ),
                "end": pd.to_datetime(
                    [
                        "2026-06-05 08:39:17.090126",
                        "2026-06-05 08:41:15.716212",
                        "2026-06-05 10:37:19.272813",
                        "2026-06-05 10:37:19.272813",
                    ]
                ),
                "hours": [9.893039575059698, 0.03295169055555558, 1.9343212781941594, 1.9343212781941594],
                "type": ["OPERATIONAL", "FAULT", "WEATHER", "IDLE"],
            }
        )

        module = "schedview.collect.observatory_state"
        with (
            mock.patch(f"{module}.get_auth", return_value=("user", "fake-token")),
            mock.patch(f"{module}.InfluxQueryClient") as mock_client,
            mock.patch(
                f"{module}.obs_status.get_observatory_state_times",
                return_value=fake_state_times,
            ) as mock_get_times,
            mock.patch(
                f"{module}.obs_status.count_observatory_states",
                return_value=(fake_state_times, expected_summary),
            ) as mock_count,
        ):
            result = get_observatory_status_summary(self.test_day_obs, self.test_day_obs_max)

        # No real web service was contacted: the client was constructed but its
        # network methods were never called directly by our function.
        mock_client.assert_called_once()
        mock_get_times.assert_called_once()
        mock_count.assert_called_once()

        # efd_client passed to get_observatory_state_times is the mocked one.
        _, get_times_kwargs = mock_get_times.call_args
        self.assertIs(get_times_kwargs["efd_client"], mock_client.return_value)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("weather_down", result.columns)
        pd.testing.assert_frame_equal(result, expected_summary)

    def test_single_day_obs_mocked(self):
        """day_obs_max=None should query a single night."""
        expected_summary = pd.DataFrame(
            {
                "night_hours": [11.860312543809414],
                "weather_down": [1.9343212781941594],
                "downtime_down": [0.0],
                "fault_down": [0.03295169055555558],
                "operational_hours": [9.893039575059698],
                "idle_down": [1.9343212781941594],
                "unknown_down": [0.0],
            },
            index=pd.Index([20260604], name="day_obs"),
        )
        module = "schedview.collect.observatory_state"
        with (
            mock.patch(f"{module}.get_auth", return_value=("user", "fake-token")),
            mock.patch(f"{module}.InfluxQueryClient"),
            mock.patch(f"{module}.obs_status.get_observatory_state_times", return_value=pd.DataFrame()),
            mock.patch(
                f"{module}.obs_status.count_observatory_states",
                return_value=(pd.DataFrame(), expected_summary),
            ) as mock_count,
        ):
            result = get_observatory_status_summary(self.test_day_obs, None)

        mock_count.assert_called_once()
        self.assertIsInstance(result, pd.DataFrame)

    @unittest.skipUnless(USE_EFD, "Skipping test that requires live EFD access")
    def test_get_observatory_status_summary_live(self):
        """Run against the real EFD web service (skipped in automated CI)."""
        result = get_observatory_status_summary(self.test_day_obs, self.test_day_obs_max)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("weather_down", result.columns)


if __name__ == "__main__":
    unittest.main()
