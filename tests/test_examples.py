import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import astropy.utils.exceptions
import astropy.utils.iers
from bs4 import BeautifulSoup

from schedview.examples.nightevents import make_night_events

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"


def _check_html(content):
    # Use trick from https://stackoverflow.com/a/77351150
    # BeautifulSoup fixes broken html, so check if it found anything to fix.
    assert content == BeautifulSoup(content, "html.parser")


class TestExamples(unittest.TestCase):

    def test_nightevents(self):
        with TemporaryDirectory() as dir:
            report = Path(dir).joinpath("nightevents.txt").name
            make_night_events("2026-03-15", report)
            with open(report) as report_io:
                content = report_io.read()
                assert len(content.split("\n")) == 12
