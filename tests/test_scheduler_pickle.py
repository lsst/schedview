import unittest
from rubin_sim.scheduler.schedulers.core_scheduler import Core_scheduler
from rubin_sim.scheduler.features.conditions import Conditions
from schedview.collect.scheduler_pickle import read_scheduler


class test_scheduler_pickle(unittest.TestCase):
    def test_read_scheduler(self):
        scheduler, conditions = read_scheduler()
        self.assertIsInstance(scheduler, Core_scheduler)
        self.assertIsInstance(conditions, Conditions)


if __name__ == "__main__":
    unittest.main()
