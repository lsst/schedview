import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers

from schedview.dayobs import DayObs
from schedview.examples.narrlog import make_narrative_log
from schedview.examples.nightevents import make_night_events
from schedview.examples.nightreport import make_nightreport
from schedview.examples.timeline import make_timeline

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

TEST_ISO_DATE = str(DayObs.from_date("2024-12-05"))
TEST_TELESCOPE = "Simonyi"
TEST_VISIT_SOURCE = "lsstcomcam"


class TestLogExamples(unittest.TestCase):

    @unittest.skip("Skipping test that requires EFD access")
    def test_nightevents(self):
        with TemporaryDirectory() as dir:
            report = str(Path(dir).joinpath("nightevents.txt").name)
            make_night_events(TEST_ISO_DATE, report)
            with open(report) as report_io:
                content = report_io.read()
                assert len(content.split("\n")) == 12

    @unittest.skip("Skipping test that requires consdb access")
    def test_narrative_log(self):
        with TemporaryDirectory() as dir:
            report = str(Path(dir).joinpath("narrlog.txt").name)
            make_narrative_log(TEST_ISO_DATE, TEST_TELESCOPE, report=report)
            assert os.path.exists(report)

    @unittest.skip("Skipping test that requires consdb access")
    def test_nightreport(self):
        with TemporaryDirectory() as dir:
            report = str(Path(dir).joinpath("nightreport.txt").name)
            make_nightreport(TEST_ISO_DATE, TEST_TELESCOPE, report=report)
            assert os.path.exists(report)

    @unittest.skip("Skipping test that requires EFD access")
    def test_timeline(self):
        with TemporaryDirectory() as dir:
            report = str(Path(dir).joinpath("timeline.html").name)
            make_timeline(TEST_ISO_DATE, TEST_VISIT_SOURCE, TEST_TELESCOPE, report=report)
            assert os.path.exists(report)
