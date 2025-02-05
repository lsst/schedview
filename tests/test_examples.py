import importlib.resources
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers
from rubin_scheduler.utils import SURVEY_START_MJD

from schedview.dayobs import DayObs
from schedview.examples.accumdepth import make_accum_depth
from schedview.examples.agemap import make_agemap
from schedview.examples.altplot import make_alt_vs_time_plot
from schedview.examples.bfrewards import make_basis_function_reward_plot
from schedview.examples.ddfcadence import make_ddf_cadence_plot
from schedview.examples.gaps import make_gaps
from schedview.examples.horizonplot import make_horizon_plot
from schedview.examples.narrlog import make_narrative_log
from schedview.examples.nightevents import make_night_events
from schedview.examples.nightreport import make_nightreport
from schedview.examples.overheadhist import make_overhead_hist
from schedview.examples.overheadtable import make_overhead_table
from schedview.examples.overheadvsslew import make_overhead_vs_slew_dist
from schedview.examples.sunmoon import make_sunmoon
from schedview.examples.surveyrewards import make_survey_reward_plot
from schedview.examples.visitmap import make_visit_map
from schedview.examples.visitparam import make_visit_param_vs_time_plot
from schedview.examples.visittable import make_visit_table

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

TEST_ISO_DATE = str(DayObs.from_date(int(SURVEY_START_MJD), int_format="mjd"))
USE_CONSDB = os.environ.get("TEST_WITH_CONSDB", "F").upper() in ("T", "TRUE", "1")


class TestExamples(unittest.TestCase):

    def test_nightevents(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("nightevents.txt").name
            make_night_events(TEST_ISO_DATE, report)
            with open(report) as report_io:
                content = report_io.read()
                assert len(content.split("\n")) == 12

    def test_gaps(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("gaps.html").name
            make_gaps(TEST_ISO_DATE, "baseline", report)
            with open(report) as report_io:
                content = report_io.read()
                assert "Open shutter" in content
                assert "Mean gap time" in content

    def test_visitmap(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("visitmaps.html").name
            make_visit_map(TEST_ISO_DATE, "baseline", 16, report=report)
            assert os.path.exists(report)

    def test_altplot(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("altplot.html").name
            make_alt_vs_time_plot(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_horizonplot(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("horizonplot.html").name
            make_horizon_plot(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_visitparam(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("visitparam.html").name
            make_visit_param_vs_time_plot(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_surveyrewards(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("surveyrewards.html").name
            rewards_uri: str = str(
                importlib.resources.files("schedview").joinpath("data").joinpath("sample_rewards.h5")
            )
            make_survey_reward_plot(TEST_ISO_DATE, rewards_uri, report=report)
            assert os.path.exists(report)

    def test_bfrewards(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("surveyrewards.html").name
            rewards_uri: str = str(
                importlib.resources.files("schedview").joinpath("data").joinpath("sample_rewards.h5")
            )
            make_basis_function_reward_plot(TEST_ISO_DATE, rewards_uri, report=report)
            assert os.path.exists(report)

    def test_accumdepth(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("accumdepth.png").name
            make_accum_depth(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_agemap(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("agemap.png").name
            make_agemap(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_ddf_cadence_plot(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("ddfcadence.html").name
            make_ddf_cadence_plot(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    @unittest.skipUnless(USE_CONSDB, "Skipping test requiring consdb access.")
    def test_narrative_log(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("narrlog.txt").name
            make_narrative_log(TEST_ISO_DATE, "Simonyi", report=report)
            assert os.path.exists(report)

    @unittest.skipUnless(USE_CONSDB, "Skipping test requiring consdb access.")
    def test_nightreport(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("nightreport.txt").name
            make_nightreport(TEST_ISO_DATE, "Simonyi", report=report)
            assert os.path.exists(report)

    def test_overhead_hist(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("overhead_hist.html").name
            make_overhead_hist(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_overhead_vs_slew_dist(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("overhead_vs_slew_dist.html").name
            make_overhead_vs_slew_dist(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_overhead_table(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("overhead_table.html").name
            make_overhead_table(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)

    def test_sunmoon(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("sunmoon.txt").name
            make_sunmoon(TEST_ISO_DATE, report=report)
            assert os.path.exists(report)

    def test_visit_table(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("visit_table.html").name
            make_visit_table(TEST_ISO_DATE, "baseline", report=report)
            assert os.path.exists(report)
