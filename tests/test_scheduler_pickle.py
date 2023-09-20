import os.path
import pickle
import unittest
from tempfile import TemporaryDirectory

from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.features.conditions import Conditions
from rubin_sim.scheduler.schedulers.core_scheduler import CoreScheduler
from rubin_sim.utils import survey_start_mjd

from schedview.collect.scheduler_pickle import read_scheduler

MJD_START = survey_start_mjd()


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


if __name__ == "__main__":
    unittest.main()
