import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_sim.data import get_baseline

from schedview.collect import find_file_resources, read_ddf_visits, read_opsim, read_rewards


class TestResources(unittest.TestCase):
    def test_find_file_resources(self):
        # Generate some test files
        test_file_names = ["foo/bar.txt", "foo/baz.txt", "foo/qux/moo.txt"]
        made_files = []
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            for file_name in test_file_names:
                file_path = temp_dir.joinpath(file_name)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                made_files.append(file_path.as_uri())
                with open(file_path, "w") as file_io:
                    file_io.write("Test content.")

            # Verify that we found exactly the files we made
            found_files = find_file_resources(temp_dir)

        assert set(made_files) == set(found_files)


class TestCollectOpsim(unittest.TestCase):
    def test_read_opsim(self):
        resource_path = ResourcePath("resource://schedview/data/")
        visits = read_opsim(resource_path)
        self.assertTrue("airmass" in visits.columns)
        self.assertGreater(len(visits), 0)

    def test_read_ddf(self):
        # Need to use the baseline, because the sample might be on a date
        # range that does not include DDFs.
        resource_path = ResourcePath(get_baseline())
        visits = read_ddf_visits(resource_path, Time("2026-11-01"), Time("2026-12-01"))
        self.assertTrue("target_name" in visits.columns)
        self.assertGreater(len(visits), 0)


class TestCollectRewards(unittest.TestCase):
    def test_read_opsim(self):
        resource_path = ResourcePath("resource://schedview/data/")
        rewards_df, obs_rewards = read_rewards(resource_path)
        self.assertGreater(len(rewards_df), 0)
        self.assertGreater(len(obs_rewards), 0)
        self.assertTrue("survey_reward" in rewards_df.columns)
        self.assertTrue(isinstance(obs_rewards, pd.Series))
