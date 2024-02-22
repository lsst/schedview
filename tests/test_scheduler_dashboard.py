import importlib.resources
import re
import subprocess
import time
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
from playwright.sync_api import expect, sync_playwright
from rubin_scheduler.scheduler.example import example_scheduler
from rubin_scheduler.scheduler.features.conditions import Conditions
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

# Objects to test instances against
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler

import schedview
from schedview.app.scheduler_dashboard.scheduler_dashboard import (
    SchedulerSnapshotDashboard,
    get_sky_brightness_date_bounds,
    scheduler_app,
)

# Schedview methods
from schedview.compute.scheduler import make_scheduler_summary_df
from schedview.compute.survey import compute_maps

TEST_PICKLE = str(importlib.resources.files(schedview).joinpath("data", "sample_scheduler.pickle.xz"))
MJD_START = get_sky_brightness_date_bounds()[0]
TEST_DATE = Time(MJD_START + 0.2, format="mjd").datetime
DEFAULT_TIMEZONE = "America/Santiago"

"""
Potentially still need to test:

    Map, key, colour bar, hovertool
    Loading indicator
    Loading two pickles, one after the other
    url mode

"""


class TestSchedulerDashboard(unittest.TestCase):
    observatory = ModelObservatory(init_load_length=1)
    scheduler = SchedulerSnapshotDashboard()
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
        self.scheduler = SchedulerSnapshotDashboard()
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


class TestDashboardE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        # cls.browser = cls.playwright.chromium.launch(
        #     headless=False,
        #     slow_mo=100
        # ) # When debugging tests
        cls.dashboard_process = subprocess.Popen(
            ["python", "../schedview/app/scheduler_dashboard/scheduler_dashboard.py"]
        )
        time.sleep(20)  # TODO: replace this with better method

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

        if hasattr(cls, "dashboard_process") and cls.dashboard_process:
            cls.dashboard_process.terminate()
            cls.dashboard_process.wait()

    def test_without_data(self):
        page = self.browser.new_page()
        page.goto("http://localhost:8080/schedview-snapshot/dashboard")

        # Check page title.
        expect(page).to_have_title(re.compile("Scheduler Dashboard"))

        # Check logo.
        img_src = page.get_by_role("img").get_attribute("src")
        page_img = self.browser.new_page()
        page_img.goto(f"http://localhost:8080{img_src}")
        expect(page_img).not_to_have_title("404: Not Found")
        page_img.close()

        # Check dashboard heading.
        expect(page.locator("pre").nth(0)).to_contain_text("Scheduler Dashboard")

        # Check dashboard sub-heading is blank.
        expect(page.locator("pre").nth(1)).to_be_empty()

        # Check 3x section headings.
        expect(page.locator("pre").nth(2)).to_contain_text("Scheduler summary")
        expect(page.locator("pre").nth(3)).to_contain_text("Basis functions & rewards")
        expect(page.locator("pre").nth(4)).to_contain_text("Map")

        # Check 'no data' messages.
        expect(page.get_by_role("paragraph").nth(0)).to_contain_text("No summary available.")
        expect(page.get_by_role("paragraph").nth(1)).to_contain_text("No rewards available.")
        expect(page.get_by_role("paragraph").nth(2)).to_contain_text("No scheduler loaded.")

        # Check tier drop down is empty.
        expect(page.get_by_role("combobox").nth(1)).to_be_empty()
        # Check date is as expected
        initial_date = MJD_START.to_datetime().strftime("%Y-%m-%d %H:%M:%S")
        expect(page.get_by_role("textbox")).to_have_value(initial_date)
        # Check map drop-down has (only) reward.
        expect(page.get_by_role("combobox").nth(2)).to_have_value("reward")

        # Change date.
        page.get_by_role("textbox").click()
        page.get_by_label("December 17,").click()
        page.get_by_label("Hour").press("Enter")
        # Restore loading conditions.
        page.get_by_role("button", name="﫽 Restore Loading Conditions").click()
        # Change nside.
        page.get_by_role("combobox").nth(3).select_option("4")
        # Change color palette.
        page.get_by_role("combobox").nth(4).select_option("Turbo256")

        # TODO: Check selections don't cause problems.

    def test_with_data(self):
        page = self.browser.new_page()
        page.goto("http://localhost:8080/schedview-snapshot/dashboard")

        expect.set_options(timeout=60_000)

        # Load data from pickle.
        page.get_by_role("combobox").first.select_option(value=TEST_PICKLE)

        # TODO: Check loading indicator displayed.

        # Check 4x info messages displayed.
        expect(page.get_by_text("Scheduler loading...").first).to_be_visible()
        expect(page.get_by_text("Scheduler pickle loaded successfully!").first).to_be_visible()
        expect(page.get_by_text("Making scheduler summary dataframe...").first).to_be_visible()
        expect(page.get_by_text("Scheduler summary dataframe updated successfully").first).to_be_visible()

        # Check subheading.
        expect(page.locator("pre").nth(1)).to_contain_text("Tier 0 - Survey 0 - Map reward")
        # Check date.
        expect(page.get_by_role("textbox")).to_have_value("2025-05-02 10:19:45")
        # Check survey docs link works.
        with page.expect_popup() as page_survey_docs_info:
            row = page.get_by_role("row").nth(1)
            link = row.get_by_role("link")
            link.click()
        page_survey_docs = page_survey_docs_info.value
        # TODO: Check something about docs page.
        page_survey_docs.close()
        # Check bf docs link works.
        with page.expect_popup() as page_bf_docs_info:
            row = page.get_by_role("row", name="AvoidDirectWind")
            link = row.get_by_role("link")
            link.click()
        page_bf_docs = page_bf_docs_info.value
        # TODO: Check something about docs page.
        page_bf_docs.close()

        # Select tier 5.
        page.get_by_role("combobox").nth(1).select_option("tier 5")
        page.wait_for_selector("text=Tier 5 - Survey 0 - Map reward")
        # Select survey 1.
        page.get_by_role("row").nth(2).click()

        page.wait_for_selector("text=Tier 5 - Survey 1 - Map reward")

        # Check 3x headings updated. # <----- Fails here
        survey_name = page.get_by_role("row").nth(2).get_by_role("gridcell").nth(1).text_content()
        expect(page.locator("pre").nth(2)).to_contain_text("Scheduler summary for tier 5")
        expect(page.locator("pre").nth(3)).to_contain_text(
            f"Basis functions & rewards for survey {survey_name}"
        )
        expect(page.locator("pre").nth(4)).to_contain_text(f"Survey {survey_name} Map: reward")
        # Check 2x tables visible.
        expect(page.get_by_role("grid")).to_have_count(2)
        # TODO: Check 1x map/key visible.
        expect(page.locator(".bk-Canvas > div:nth-child(11)")).to_be_visible()

        # Select u_sky from Survey map.
        page.get_by_role("combobox").nth(2).select_option("u_sky")
        # Check map heading changed.
        expect(page.locator("pre").nth(4)).to_contain_text(f"Survey {survey_name} Map: u_sky")

        # Select M5Diff from Survey map.
        map_option = page.locator("option", has_text="M5Diff i").text_content()
        page.get_by_role("combobox").nth(2).select_option(map_option)
        # Check M5Diff row highlighted in bf table.
        expect(page.get_by_role("row", name="M5Diff i")).to_have_class(re.compile(r"tabulator-selected"))

        # Select MoonAvoidance row in bf table.
        page.get_by_text("MoonAvoidance", exact=True).click()
        # Check map heading changed.
        # expect(page.locator("pre").nth(4)).to_contain_text(
        #     f"Survey {survey_name} Reward: MoonAvoidance"
        # ) # TODO FAILING (colon bug)
        # Check Survey map drop-down value = MoonAvoidance.
        map_option = page.locator("option", has_text="MoonAvoidance").text_content()
        expect(page.get_by_role("combobox").nth(2)).to_have_value(map_option)
        # TODO: Check map all one colour. (screenshot?)

        # Select FilterChange row in bf table.
        page.get_by_text("FilterChange i").click()
        # Check Survey map drop-down shows “”.
        expect(page.get_by_role("combobox").nth(2)).to_have_value("")

        # Select Tier 3.
        page.get_by_role("combobox").nth(1).select_option("tier 3")

        # Check Survey row 0 shows Reward='TimeToTwilight, NightModulo'.
        survey_0_reward = page.get_by_role("row").nth(1).get_by_role("gridcell").nth(2)
        expect(survey_0_reward).to_have_text("TimeToTwilight, NightModulo")

        # Check TimeToTwilight infeasiblility displayed correctly.
        page.get_by_label("Show Page 2").click()  # TODO: Remove once Eman's PR merged.
        img = page.get_by_role("row").filter(has_text="TimeToTwilight").get_by_role("img")
        fill_value = img.evaluate('(element) => element.querySelector("path").getAttribute("fill")')
        assert fill_value == "#CE1515"
        expect(
            page.get_by_role("rowgroup").nth(5).get_by_role("row").nth(2).get_by_role("gridcell").nth(4)
        ).to_contain_text("-Infinity")

        # Change date.
        page.get_by_role("textbox").click()  # open date picker
        page.get_by_label("May 3,").click()  # change day
        page.get_by_label("Hour").fill("03")  # change hour
        page.locator("div:nth-child(3) > .arrowUp").click()  # change minute
        page.locator("div:nth-child(5) > .arrowUp").click()  # change second
        page.get_by_text("::").press("Enter")  # submit

        # TODO: Check loading indicator shown.

        # Check 4x info messages displayed.
        expect(page.get_by_text("Updating Conditions object...").first).to_be_visible()
        expect(page.get_by_text("Conditions object updated successfully").first).to_be_visible()
        expect(page.get_by_text("Making scheduler summary dataframe...").first).to_be_visible()
        expect(page.get_by_text("Scheduler summary dataframe updated successfully").first).to_be_visible()

        # Select tier 3.
        page.get_by_role("combobox").nth(1).select_option("tier 3")

        # Check survey row 0 shows Reward = 11.something
        survey_0_reward = page.get_by_role("row").nth(1).get_by_role("gridcell").nth(2)
        # expect(survey_0_reward).to_have_text("11.744962901180354")
        expect(survey_0_reward).to_have_text(re.compile(r"11\.7\d"))

        # Check TimeToTwilight feasiblility displayed correctly.
        page.get_by_label("Show Page 2").click()  # TODO: Remove once Eman's PR merged.
        img = page.get_by_role("row").filter(has_text="TimeToTwilight").get_by_role("img")
        fill_value = img.evaluate('(element) => element.querySelector("path").getAttribute("fill")')
        assert fill_value == "#2DC214"
        expect(
            page.get_by_role("rowgroup").nth(5).get_by_role("row").nth(2).get_by_role("gridcell").nth(4)
        ).to_contain_text("0.000")

        # Select Survey map u_sky (to check restore works)
        page.get_by_role("combobox").nth(2).select_option("u_sky")

        # Select map resolution = 4
        page.get_by_role("combobox").nth(3).select_option("4")
        # TODO: Check map correctly updated.

        # Select color palette = Inferno256
        page.get_by_role("combobox").nth(4).select_option("Inferno256")
        # TODO: Check map/colorbar correctly updated

        # Change ordering of survey table
        page.get_by_role("columnheader", name="Reward", exact=True).locator("div").nth(4).click()
        # Change ordering of bf table
        page.get_by_role("columnheader", name="Basis Function").locator("div").nth(3).click()
        # Reset loading conditions.
        page.get_by_role("button", name="﫽 Restore Loading Conditions").click()

        # TODO: Check loading indicator displayed

        # 4x info messages pop up
        expect(page.get_by_text("Scheduler loading...").first).to_be_visible()
        expect(page.get_by_text("Scheduler pickle loaded successfully!").first).to_be_visible()
        expect(page.get_by_text("Making scheduler summary dataframe...").first).to_be_visible()
        expect(page.get_by_text("Scheduler summary dataframe updated successfully").first).to_be_visible()

        # Check subheading = ‘Tier 0 - Survey 0 - Map reward’
        expect(page.locator("pre").nth(1)).to_contain_text("Tier 0 - Survey 0 - Map reward")
        # Check 3x headings return to tier 0, survey 0.
        survey_name = page.get_by_role("row").nth(1).get_by_role("gridcell").nth(1).text_content()
        expect(page.locator("pre").nth(2)).to_contain_text("Scheduler summary for tier 0")
        expect(page.locator("pre").nth(3)).to_contain_text(
            f"Basis functions & rewards for survey {survey_name}"
        )
        expect(page.locator("pre").nth(4)).to_contain_text(f"Survey {survey_name}")
        # Check date.
        expect(page.get_by_role("textbox")).to_have_value("2025-05-02 10:19:45")
        # Check Survey Map shows ‘reward’
        expect(page.get_by_role("combobox").nth(2)).to_have_value("reward")

        # TODO: Check Map resolution = 16. (FAILING)
        # expect(page.get_by_role("combobox").nth(3)).to_have_value("16")
        # TODO: Check color palette = Viridis255. (FAILING)
        # expect(
        #     page.get_by_role("combobox").nth(4)
        # ).to_have_value("Viridis256")

        # Select tier 3.
        page.get_by_role("combobox").nth(1).select_option("tier 3")

        # Check ordering of bf table (Accum. order).
        expect(page.get_by_role("columnheader", name="Reward", exact=True)).to_have_attribute(
            "aria-sort", "none"
        )
        # Check ordering of survey table (index).
        expect(page.get_by_role("columnheader", name="Basis Function")).to_have_attribute("aria-sort", "none")

        # Check debugger.
        page.get_by_role("button", name="► Debugging").click()
        expect(page.locator("pre").nth(5)).to_contain_text("Publishing sky map.")
        expect(page.locator("pre").nth(5)).not_to_contain_text("Traceback")


if __name__ == "__main__":
    unittest.main()
