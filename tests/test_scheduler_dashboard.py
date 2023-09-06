import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
import bokeh.plotting
import bokeh.io

from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.example import example_scheduler

from schedview.app.scheduler_dashboard.scheduler_dashboard import (Scheduler, scheduler_app)

# Schedview methods
from schedview.collect.scheduler_pickle import read_scheduler
from schedview.compute.scheduler import make_scheduler_summary_df
from schedview.compute.survey import make_survey_reward_df, compute_maps

# Objects to test instances against
from rubin_sim.scheduler.schedulers.core_scheduler import CoreScheduler
from rubin_sim.scheduler.features.conditions import Conditions
from panel.widgets import Tabulator
from collections import OrderedDict
import pandas as pd

from astropy.time import Time
from pandas import Timestamp
from zoneinfo import ZoneInfo
from datetime import datetime

"""
Tests I usually perform:

    1. Load valid pickle.
    2. Choose date.
    3. Choose tier.
    4. Select survey.
    5. Select basis function (array).
    6. Select basis function (finite scalar).
    7. Select basis function (-inf scalar).
    8. Choose survey map (basis function).
    9. Choose survey map (sky brightness).
   10. Choose nside.
   11. Choose color palette.
   12. Check tooltip reflects selection data.
   13. Choose invalid date.
   14. Choose invalid pickle.
   15. Load two pickles, one after the other.


Notes
-----

    - Unit tests are not supposed to rely on each other.
    - Unit tests are run in alphabetical order.

"""

TEST_PICKLE = "/Users/me/Documents/2023/ADACS/Panel_scheduler/Rubin_scheduler_dashboard/example_pickle_scheduler.p.xz"
TEST_DATE = datetime(2023, 8, 1, 23, 0)
DEFAULT_TIMEZONE = 'America/Santiago'


class test_scheduler_dashboard(unittest.TestCase):

    observatory = ModelObservatory()
    scheduler = Scheduler()
    scheduler.scheduler_fname = TEST_PICKLE
    scheduler._date_time = Time(Timestamp(TEST_DATE, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))).mjd

    def test_scheduler_app(self):
        app = scheduler_app(date=TEST_DATE, scheduler_pickle=TEST_PICKLE)
        app_bokeh_model = app.get_root()
        with TemporaryDirectory() as dir:
            out_path = Path(dir)
            saved_html_fname = out_path.joinpath("test_page.html")
            bokeh.plotting.output_file(filename=saved_html_fname, title="Test Page")
            bokeh.plotting.save(app_bokeh_model)

    def test_read_scheduler(self):
        self.scheduler.read_scheduler()
        self.assertIsInstance(self.scheduler._scheduler, CoreScheduler)
        self.assertIsInstance(self.scheduler._conditions, Conditions)

    def test_title(self):
        self.scheduler._tier = "tier 2"
        self.scheduler._survey = 3
        self.scheduler._display_dashboard_data = True
        self.scheduler._display_dashboard_data = True
        title = self.scheduler.generate_dashboard_title()
        expected_title = f'\nTier {self.scheduler._tier[-1]} - Survey {self.scheduler._survey} - Map {self.scheduler.survey_map}'
        self.assertEqual(title, expected_title)

    def test_make_summary_df(self):
        self.scheduler._scheduler = example_scheduler()
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler.make_summary_df()
        self.assertIsInstance(self.scheduler._survey_rewards, pd.DataFrame)

    def test_survey_widget(self):
        self.scheduler._scheduler = example_scheduler()
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler._scheduler.update_conditions(self.scheduler._conditions)
        survey_rewards = make_scheduler_summary_df(
            self.scheduler._scheduler,
            self.scheduler._conditions,
            self.scheduler._scheduler.make_reward_df(self.scheduler._conditions)
            )
        survey_rewards['survey'] = survey_rewards.loc[:, 'survey_name']
        self.scheduler._survey_rewards = survey_rewards
        self.scheduler.create_survey_tabulator_widget()
        widget = self.scheduler.publish_survey_tabulator_widget()
        self.assertIsInstance(widget, Tabulator)

    def test_compute_survey_maps(self):
        self.scheduler._scheduler = example_scheduler()
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler._scheduler.update_conditions(self.scheduler._conditions)
        survey = self.scheduler._scheduler.survey_lists[2][3]
        survey_maps = compute_maps(survey, self.scheduler._conditions, nside=8)
        self.assertIsInstance(survey_maps, OrderedDict)
        self.assertIn("reward", survey_maps)
        self.assertIn("g_sky", survey_maps)


if __name__ == "__main__":
    unittest.main()
