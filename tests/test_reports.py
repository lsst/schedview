import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

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
        assert set(reports.columns) == {"report", "fname", "report_time", "night", "link", "url"}
        assert len(reports) == len(self.test_report_fnames)

    def test_make_report_link_table(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        html_table = schedview.reports.make_report_link_table(reports)
        # Make sure we can parse the result as XML
        ET.fromstring(html_table)

    def test_make_report_rss_feed(self):
        reports = schedview.reports.find_reports(self.temp_dir.name)
        test_file = Path(self.temp_dir.name).joinpath("test.rss")
        rss_tree = schedview.reports.make_report_rss_feed(reports, str(test_file), 99999)
        assert isinstance(rss_tree, ET.ElementTree)
        # See if we can parse the result as XML
        ET.parse(str(test_file))
