import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers

from schedview.examples.gaps import make_gaps
from schedview.examples.nightevents import make_night_events

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"


class TestExamples(unittest.TestCase):

    def test_nightevents(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("nightevents.txt").name
            make_night_events("2026-03-15", report)
            with open(report) as report_io:
                content = report_io.read()
                assert len(content.split("\n")) == 12

    def test_gaps(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("gaps.html").name
            make_gaps("2026-03-15", "baseline", report)
            with open(report) as report_io:
                content = report_io.read()
                assert "Open shutter" in content
                assert "Mean gap time" in content
