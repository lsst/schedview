"""Black-box tests for schedview.reports public API."""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

import schedview.reports


class TestReports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_report_fnames = []
        cls.temp_dir = TemporaryDirectory()
        year, month = "2025", "06"
        cls.reports = ("prenight", "nightsum")
        cls.instruments = ("lsstcam", "auxtel")
        cls.days = ("20", "21")

        for report in cls.reports:
            for instrument in cls.instruments:
                for day in cls.days:
                    test_dir = Path(cls.temp_dir.name).joinpath(report, instrument, year, month, day)
                    test_dir.mkdir(parents=True)
                    test_file = test_dir.joinpath(f"{report}_{year}-{month}-{day}.html")
                    cls.test_report_fnames.append(test_file)
                    open(test_file, "a").close()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_find_reports(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        assert set(reports.columns) == {
            "report",
            "fname",
            "report_time",
            "night",
            "link",
            "url",
        }
        assert len(reports) == len(self.test_report_fnames)

    def test_make_report_link_table(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        html_table = schedview.reports.make_report_link_table(reports)
        # Make sure we can parse the result as XML
        ET.fromstring(html_table)

    def test_make_report_link_table_with_visits(self):
        rng = np.random.default_rng(0)
        n = 40
        # Match dayObs values used for test reports
        dayobs = np.array([20250620] * 20 + [20250621] * 20)
        visits = pd.DataFrame(
            {
                "dayObs": dayobs,
                "observationId": np.arange(n),
                "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n),
                "eff_time_median": rng.uniform(20.0, 40.0, size=n),
                "exp_time": rng.uniform(25.0, 35.0, size=n),
                "band": rng.choice(list("ugrizy"), size=n),
                "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
                "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        html_table = schedview.reports.make_report_link_table(reports, visits=visits)
        # Must be parseable as XML
        ET.fromstring(html_table)
        # Summary column headers must appear in the output
        assert "Total" in html_table
        assert "science" in html_table

    def test_make_report_rss_feed(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        test_file = Path(self.temp_dir.name).joinpath("test.rss")
        rss_tree = schedview.reports.make_report_rss_feed(reports, str(test_file), 99999)
        assert isinstance(rss_tree, ET.ElementTree)
        # See if we can parse the result as XML
        ET.parse(str(test_file))

    def test_make_report_rss_feed_has_band_breakdown(self):
        import re

        rng = np.random.default_rng(0)
        n = 40
        # Match dayObs values used for test reports
        dayobs = np.array([20250620] * 20 + [20250621] * 20)
        visits = pd.DataFrame(
            {
                "dayObs": dayobs,
                "observationId": np.arange(n),
                "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n),
                "eff_time_median": rng.uniform(20.0, 40.0, size=n),
                "exp_time": rng.uniform(25.0, 35.0, size=n),
                "band": rng.choice(list("ugrizy"), size=n),
                "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
                "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        rss_tree = schedview.reports.make_report_rss_feed(reports, fname=None, max_days=99999, visits=visits)
        descriptions = [d.text or "" for d in rss_tree.getroot().iterfind("channel/item/description")]
        joined = "\n".join(descriptions)
        # The total visit line must carry a parenthetical band breakdown.
        assert re.search(r"Total visits: \d+ \(\d+[ugrizy]", joined)
        # The science line carries a band breakdown only when there are science
        # visits. Whether a program counts as science depends on the default
        # SCIENCE_PROGRAMS, which is empty unless rubin_nights is installed, so
        # only assert the breakdown format when science visits are present.
        if re.search(r"Science visits: [1-9]", joined):
            assert re.search(r"Science visits: \d+ \(\d+[ugrizy]", joined)

    def test_make_report_rss_feed_uses_title_parameter(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        channel_title = "Custom Schedview Reports"
        rss_tree = schedview.reports.make_report_rss_feed(
            reports,
            fname=None,
            max_days=99999,
            title=channel_title,
        )
        root = rss_tree.getroot()
        title_elem = root.find("channel/title")
        assert title_elem is not None
        assert title_elem.text == channel_title
