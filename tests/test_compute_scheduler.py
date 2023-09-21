import unittest

import pandas as pd
import rubin_sim.scheduler.example
from astropy.time import Time
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.features.conditions import Conditions
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.utils import survey_start_mjd

from schedview.compute.scheduler import create_example, make_scheduler_summary_df, make_unique_survey_name

MJD_START = survey_start_mjd()
TEST_MJD = MJD_START + 0.2


class TestComputeScheduler(unittest.TestCase):
    sample_scheduler = example_scheduler(mjd_start=MJD_START)
    observatory = ModelObservatory()

    def test_create_example(self):
        current_time = Time(TEST_MJD, format="mjd").iso[:19] + "Z"
        survey_start = Time(MJD_START, format="mjd").iso[:19] + "Z"
        scheduler, observatory, conditions, observations = create_example(current_time, survey_start)
        self.assertIsInstance(scheduler, rubin_sim.scheduler.schedulers.CoreScheduler)
        self.assertIsInstance(observatory, ModelObservatory)
        self.assertIsInstance(conditions, Conditions)

    def test_make_unique_survey_name(self):
        names = []
        for tier, tier_list in enumerate(self.sample_scheduler.survey_lists):
            for survey_id, survey in enumerate(tier_list):
                name = make_unique_survey_name(self.sample_scheduler, [tier, survey_id])
                names.append(name)

        self.assertEqual(len(names), len(set(names)))

    def test_make_scheduler_summary_df(self):
        self.observatory.mjd = MJD_START
        conditions = self.observatory.return_conditions()
        reward_df = self.sample_scheduler.make_reward_df(conditions)
        summary_df = make_scheduler_summary_df(self.sample_scheduler, conditions, reward_df)
        self.assertIsInstance(summary_df, pd.DataFrame)
