import unittest
import pandas as pd
from schedview.compute.survey import make_survey_reward_df
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.example import example_scheduler


class TestComputeSurvey(unittest.TestCase):
    def test_make_survey_reward_df(self):
        scheduler = example_scheduler()
        observatory = ModelObservatory()
        observatory.mjd = 60100.2
        conditions = observatory.return_conditions()
        reward_df = make_survey_reward_df(scheduler, conditions)
        self.assertIsInstance(reward_df, pd.DataFrame)
