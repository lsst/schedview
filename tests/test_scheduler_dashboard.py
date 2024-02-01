import importlib.resources
import unittest
from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import bokeh.io
import bokeh.plotting
import pandas as pd
import rubin_scheduler.site_models
from astropy.time import Time
from pandas import Timestamp
from panel.widgets import Tabulator
from rubin_scheduler.scheduler.example import example_scheduler
from rubin_scheduler.scheduler.features.conditions import Conditions
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

# Objects to test instances against
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler

import schedview
from schedview.app.scheduler_dashboard.scheduler_dashboard import (
    Scheduler,
    get_sky_brightness_date_bounds,
    scheduler_app,
)

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

    - Unit tests are not supposed to rely on each other.
    - Unit tests are run in alphabetical order.

"""

TEST_PICKLE = str(importlib.resources.files(schedview).joinpath("data", "sample_scheduler.pickle.xz"))
MJD_START = get_sky_brightness_date_bounds()[0]
TEST_DATE = Time(MJD_START + 0.2, format="mjd").datetime
DEFAULT_TIMEZONE = "America/Santiago"


class TestSchedulerDashboard(unittest.TestCase):
    observatory = ModelObservatory(init_load_length=1)
    scheduler = Scheduler()
    scheduler.scheduler_fname = TEST_PICKLE
    scheduler._mjd = Time(Timestamp(TEST_DATE, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))).mjd

    def setUp(self) -> None:
        bokeh.io.reset_output()

    def test_scheduler_app(self):
        sched_app = scheduler_app(date_time=TEST_DATE, scheduler_pickle=TEST_PICKLE, data_from_urls=True)
        sched_app_bokeh_model = sched_app.get_root()
        with TemporaryDirectory() as scheduler_dir:
            sched_out_path = Path(scheduler_dir)
            sched_saved_html_fname = sched_out_path.joinpath("sched_test_page.html")
            bokeh.plotting.output_file(filename=sched_saved_html_fname, title="Scheduler Test Page")
            bokeh.plotting.save(sched_app_bokeh_model)
        bokeh.io.reset_output()

    def test_read_scheduler(self):
        self.scheduler = Scheduler()
        self.scheduler.scheduler_fname = TEST_PICKLE
        self.scheduler._mjd = Time(Timestamp(TEST_DATE, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))).mjd
        self.scheduler.read_scheduler()
        self.assertIsInstance(self.scheduler._scheduler, CoreScheduler)
        self.assertIsInstance(self.scheduler._conditions, Conditions)

    def test_title(self):
        self.scheduler._tier = "tier 2"
        self.scheduler._survey = 0
        self.scheduler.param["survey_map"].objects = ["reward"]
        self.scheduler.survey_map = "reward"
        self.scheduler._map_name = "reward"
        self.scheduler._display_dashboard_data = True
        title = self.scheduler.generate_dashboard_subtitle()
        tier = self.scheduler._tier[-1]
        survey = self.scheduler._survey
        survey_map = self.scheduler.survey_map
        expected_title = f"\nTier {tier} - Survey {survey} - Map {survey_map}"
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
        scheduler_summary_df["survey"] = scheduler_summary_df.loc[:, "survey_name_with_id"]
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

    def test_site_models(self):
        wind_speed = 4
        wind_direction = 25
        fiducial_seeing = 0.69
        wind_data = rubin_scheduler.site_models.ConstantWindData(
            wind_speed=wind_speed,
            wind_direction=wind_direction,
        )
        seeing_data = rubin_scheduler.site_models.ConstantSeeingData(fiducial_seeing)
        self.assertIsInstance(wind_data, rubin_scheduler.site_models.ConstantWindData)
        self.assertIsInstance(seeing_data, rubin_scheduler.site_models.ConstantSeeingData)
        self.assertEqual(wind_data.wind_speed, wind_speed)
        self.assertEqual(wind_data.wind_direction, wind_direction)
        self.assertEqual(seeing_data.fwhm_500, fiducial_seeing)


if __name__ == "__main__":
    unittest.main()
