import importlib.resources
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import bokeh

import schedview
import schedview.collect.rewards
import schedview.plot.rewards

WRITE_TIMEOUT_SECONDS = 20


class TestPlotRewards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        # Even though this seems unnecessary given the filename argument used
        # in verify_can_plot, without it tests fail when they are run in CI
        # by github (but run locally).
        saved_html_fname = cls.temp_path.joinpath(f"test_plot_rewards_{time.time()}.html").name
        bokeh.plotting.output_file(filename=saved_html_fname, title="This Test Page")

    def verify_can_plot(self, plot):
        saved_html_fname = self.temp_path.joinpath(f"can_verify_plot_test_{time.time()}.html").name
        bokeh.io.save(plot, filename=saved_html_fname)
        waited_time_seconds = 0
        while waited_time_seconds < WRITE_TIMEOUT_SECONDS and not os.path.isfile(saved_html_fname):
            time.sleep(1)

    def setUp(self):
        rewards_rp = importlib.resources.files("schedview").joinpath("data").joinpath("sample_rewards.h5")
        self.rewards_df, self.obs_reward = schedview.collect.rewards.read_rewards(rewards_rp)
        self.tier = 3
        self.day_obs_mjd = int(self.rewards_df["queue_start_mjd"].min() - 0.5)

    def test_reward_timeline_for_tier(self):
        plot = schedview.plot.rewards.reward_timeline_for_tier(
            self.rewards_df, tier=self.tier, day_obs_mjd=self.day_obs_mjd
        )
        self.verify_can_plot(plot)

    def test_area_timeline_for_tier(self):
        plot = schedview.plot.rewards.area_timeline_for_tier(
            self.rewards_df, tier=self.tier, day_obs_mjd=self.day_obs_mjd
        )
        self.verify_can_plot(plot)

    def test_reward_timeline_for_surveys(self):
        plot = schedview.plot.rewards.reward_timeline_for_surveys(
            self.rewards_df, day_obs_mjd=self.day_obs_mjd
        )
        self.verify_can_plot(plot)


if __name__ == "__main__":
    unittest.main()
