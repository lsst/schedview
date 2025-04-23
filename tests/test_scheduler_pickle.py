import os.path
import pickle
import unittest
from tempfile import TemporaryDirectory

from rubin_scheduler.scheduler.example import example_scheduler
from rubin_scheduler.scheduler.features.conditions import Conditions
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler
from rubin_scheduler.utils import SURVEY_START_MJD

from schedview.collect import read_scheduler

MJD_START = SURVEY_START_MJD


class TestSchedulerPickle(unittest.TestCase):
    def test_read_scheduler(self):
        scheduler, conditions = read_scheduler()
        self.assertIsInstance(scheduler, CoreScheduler)
        self.assertIsInstance(conditions, Conditions)

    def test_bare_scheduler(self):
        # Read a file with just a scheduler, no conditions
        raw_scheduler = example_scheduler(mjd_start=MJD_START)
        with TemporaryDirectory() as data_dir:
            sample_path = os.path.join(data_dir, "sample_scheduler.pickle")
            with open(sample_path, "wb") as file_io:
                pickle.dump(raw_scheduler, file_io)

            scheduler, conditions = read_scheduler(sample_path)

        self.assertIsInstance(scheduler, CoreScheduler)
        self.assertIsInstance(conditions, Conditions)

    def test_extra_scheduler(self):
        # Test if we can read a pickle with extra stuff in it.
        scheduler, conditions = read_scheduler()
        extra_content = "I am a fish."
        with TemporaryDirectory() as data_dir:
            content = (scheduler, conditions, extra_content)
            sample_path = os.path.join(data_dir, "sample_scheduler.pickle")
            with open(sample_path, "wb") as file_io:
                pickle.dump(content, file_io)

            scheduler, conditions = read_scheduler(sample_path)

        self.assertIsInstance(scheduler, CoreScheduler)
        self.assertIsInstance(conditions, Conditions)


if __name__ == "__main__":
    unittest.main()
