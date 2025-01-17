import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers
from rubin_scheduler.utils import SURVEY_START_MJD

from schedview.dayobs import DayObs
from schedview.examples.gaps import make_gaps
from schedview.examples.nightevents import make_night_events
from schedview.examples.visitmap import make_visit_map

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
