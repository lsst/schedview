import unittest
from collections import OrderedDict

import pandas as pd
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.utils import survey_start_mjd

from schedview.compute.survey import compute_maps, make_survey_reward_df

MJD_START = survey_start_mjd()
TEST_MJD = MJD_START + 0.2


class TestComputeSurvey(unittest.TestCase):
    scheduler = example_scheduler(mjd_start=MJD_START)
    observatory = ModelObservatory()

    def test_make_survey_reward_df(self):
        self.observatory.mjd = TEST_MJD
        conditions = self.observatory.return_conditions()
        reward_df = make_survey_reward_df(self.scheduler, conditions)
        self.assertIsInstance(reward_df, pd.DataFrame)

    def test_compute_maps(self):
        self.observatory.mjd = TEST_MJD
        conditions = self.observatory.return_conditions()
        survey = self.scheduler.survey_lists[2][2]
        survey_maps = compute_maps(survey, conditions, nside=8)
        self.assertIsInstance(survey_maps, OrderedDict)
        self.assertIn("reward", survey_maps)
        self.assertIn("g_sky", survey_maps)
