import importlib.resources
import unittest
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import bokeh.io
import bokeh.plotting
import pandas as pd
from astropy.time import Time
from pandas import Timestamp
from panel.widgets import Tabulator
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.features.conditions import Conditions
from rubin_sim.scheduler.model_observatory import ModelObservatory

# Objects to test instances against
from rubin_sim.scheduler.schedulers.core_scheduler import CoreScheduler
from rubin_sim.utils import survey_start_mjd

import schedview
from schedview.app.scheduler_dashboard.scheduler_dashboard import Scheduler, scheduler_app

# Schedview methods
from schedview.compute.scheduler import make_scheduler_summary_df
from schedview.compute.survey import compute_maps

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

TEST_PICKLE = str(importlib.resources.files(schedview).joinpath("data", "sample_scheduler.pickle.xz"))
MJD_START = survey_start_mjd()
TEST_DATE = Time(MJD_START + 0.2, format="mjd").datetime
DEFAULT_TIMEZONE = "America/Santiago"


class TestSchedulerDashboard(unittest.TestCase):
    observatory = ModelObservatory(init_load_length=1)
    scheduler = Scheduler()
    scheduler.scheduler_fname = TEST_PICKLE
    scheduler._date_time = Time(Timestamp(TEST_DATE, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))).mjd

    @unittest.skip("Skipping so it does not block implementation of CI")
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
        self.scheduler._survey = 0
        self.scheduler._display_dashboard_data = True
        title = self.scheduler.generate_dashboard_subtitle()
        tier = self.scheduler._tier[-1]
        survey = self.scheduler._survey
        survey_map = self.scheduler.survey_map
        expected_title = f"\nTier {tier} - Survey {survey} - Reward {survey_map}"
        self.assertEqual(title, expected_title)

    def test_make_summary_df(self):
        self.scheduler._scheduler = example_scheduler(mjd_start=MJD_START)
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler.make_scheduler_summary_df()
        self.assertIsInstance(self.scheduler._scheduler_summary_df, pd.DataFrame)

    def test_summary_widget(self):
        self.scheduler._scheduler = example_scheduler(mjd_start=MJD_START)
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler._scheduler.update_conditions(self.scheduler._conditions)
        scheduler_summary_df = make_scheduler_summary_df(
            self.scheduler._scheduler,
            self.scheduler._conditions,
            self.scheduler._scheduler.make_reward_df(self.scheduler._conditions),
        )
        scheduler_summary_df["survey"] = scheduler_summary_df.loc[:, "survey_name"]
        self.scheduler.scheduler_summary_df = scheduler_summary_df
        self.scheduler.create_summary_widget()
        widget = self.scheduler.publish_summary_widget()
        self.assertIsInstance(widget, Tabulator)

    def test_compute_survey_maps(self):
        self.scheduler._scheduler = example_scheduler(mjd_start=MJD_START)
        self.scheduler._conditions = self.observatory.return_conditions()
        self.scheduler._scheduler.update_conditions(self.scheduler._conditions)
        survey = self.scheduler._scheduler.survey_lists[2][3]
        survey_maps = compute_maps(survey, self.scheduler._conditions, nside=8)
        self.assertIsInstance(survey_maps, OrderedDict)
        self.assertIn("reward", survey_maps)
        self.assertIn("g_sky", survey_maps)


if __name__ == "__main__":
    unittest.main()
