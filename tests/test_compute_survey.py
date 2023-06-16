import unittest
from collections import OrderedDict
import pandas as pd
from schedview.compute.survey import make_survey_reward_df, compute_maps
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.example import example_scheduler


class TestComputeSurvey(unittest.TestCase):
    scheduler = example_scheduler()
    observatory = ModelObservatory()

    def test_make_survey_reward_df(self):
        self.observatory.mjd = 60100.2
        conditions = self.observatory.return_conditions()
        reward_df = make_survey_reward_df(self.scheduler, conditions)
        self.assertIsInstance(reward_df, pd.DataFrame)

    def test_compute_maps(self):
        self.observatory.mjd = 60100.2
        conditions = self.observatory.return_conditions()
        survey = self.scheduler.survey_lists[2][2]
        survey_maps = compute_maps(survey, conditions, nside=8)
        self.assertIsInstance(survey_maps, OrderedDict)
        self.assertIn("reward", survey_maps)
        self.assertIn("g_sky", survey_maps)
