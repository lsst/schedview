import importlib.resources
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers
from rubin_scheduler.utils import SURVEY_START_MJD

from schedview.dayobs import DayObs
from schedview.examples.altplot import make_alt_vs_time_plot
from schedview.examples.gaps import make_gaps
from schedview.examples.horizonplot import make_horizon_plot
from schedview.examples.nightevents import make_night_events
from schedview.examples.surveyrewards import make_survey_reward_plot
from schedview.examples.visitmap import make_visit_map
from schedview.examples.visitparam import make_visit_param_vs_time_plot

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

TEST_ISO_DATE = str(DayObs.from_date(int(SURVEY_START_MJD), int_format="mjd"))


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
