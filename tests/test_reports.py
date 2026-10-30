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

    def test_make_report_rss_feed_prenight_description(self):
        import re

        rng = np.random.default_rng(0)
        n = 40
        # Match dayObs values used for test reports. Prenight-simulation
        # visits carry t_eff and visitExposureTime rather than
        # eff_time_median and exp_time.
        dayobs = np.array([20250620] * 20 + [20250621] * 20)
        prenight_visits = pd.DataFrame(
            {
                "dayObs": dayobs,
                "observationId": np.arange(n),
                "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n),
                "t_eff": rng.uniform(20.0, 40.0, size=n),
                "visitExposureTime": rng.uniform(25.0, 35.0, size=n),
                "band": rng.choice(list("ugrizy"), size=n),
                "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
                "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        rss_tree = schedview.reports.make_report_rss_feed(
            reports, fname=None, max_days=99999, prenight_visits=prenight_visits
        )
        root = rss_tree.getroot()
        # Collect descriptions for prenight items only (via category).
        prenight_descs = []
        for item in root.iterfind("channel/item"):
            category = item.findtext("category") or ""
            if category == "lsstcam_prenight":
                prenight_descs.append(item.findtext("description") or "")
        joined = "\n".join(prenight_descs)
        # The prenight items must carry a populated summary description
        # using the distinct prenight format (no separate "Science visits"
        # line since all prenight visits are science).
        assert re.search(r"Simulated \(science\) visits: \d+ \(\d+[ugrizy]", joined)
        assert "First simulated visit:" not in joined

    def test_prenight_first_visit_coordinates_and_regressions(self):
        visits = pd.DataFrame(
            {
                "dayObs": [20250620, 20250621, 20250620, 20250621],
                "observationId": [0, 1, 2, 3],
                "seeingFwhmGeom": [1.0] * 4,
                "t_eff": [30.0] * 4,
                "visitExposureTime": [30.0] * 4,
                "band": ["r"] * 4,
                "science_program": ["BLOCK-365"] * 4,
                "target_name": ["COSMOS"] * 4,
                "observationStartMJD": [60846.2, 60847.2, 60846.1, 60847.1],
                "fieldRA": [1.0, 2.0, 123.456, 234.567],
                "fieldDec": [1.0, 2.0, -45.678, -34.567],
                "altitude": [1.0, 2.0, 60.123, 70.123],
                "azimuth": [1.0, 2.0, 210.3456, 220.3456],
            }
        )
        observed = visits.rename(columns={"t_eff": "eff_time_median", "visitExposureTime": "exp_time"})
        reports = schedview.reports.find_reports(self.temp_dir.name)

        def make_feed(prenight_visits):
            return schedview.reports.make_report_rss_feed(
                reports,
                max_days=99999,
                visits=observed,
                prenight_visits=prenight_visits,
                science_programs=("BLOCK-365",),
            ).getroot()

        baseline = make_feed(None)
        root = make_feed(visits)
        repeated = make_feed(visits.copy())
        changed = visits.copy()
        changed.loc[2, "fieldRA"] = 124.456
        changed_root = make_feed(changed)
        assert root.findtext("channel/description") == baseline.findtext("channel/description")
        expected_lines = {
            "2025-06-20": (
                "First simulated visit: RA=123.46 deg, decl=-45.68 deg, " "alt=60.12 deg, az=210.35 deg;"
            ),
            "2025-06-21": (
                "First simulated visit: RA=234.57 deg, decl=-34.57 deg, " "alt=70.12 deg, az=220.35 deg;"
            ),
        }
        for base_item, item, repeat_item, changed_item in zip(
            baseline.iterfind("channel/item"),
            root.iterfind("channel/item"),
            repeated.iterfind("channel/item"),
            changed_root.iterfind("channel/item"),
            strict=True,
        ):
            description = item.findtext("description") or ""
            title = item.findtext("title")
            assert item.findtext("guid") == repeat_item.findtext("guid")
            if item.findtext("category") == "lsstcam_prenight":
                night = title.rsplit(" ", 1)[-1]
                assert expected_lines[night] in description.splitlines()
                if night == "2025-06-20":
                    assert item.findtext("guid") != changed_item.findtext("guid")
                else:
                    assert item.findtext("guid") == changed_item.findtext("guid")
            else:
                assert description == (base_item.findtext("description") or "")
                assert "First simulated visit:" not in description
                assert item.findtext("guid") == changed_item.findtext("guid")
        assert schedview.reports.make_report_link_table(
            reports, visits=observed
        ) == schedview.reports.make_report_link_table(
            reports, visits=observed.drop(columns=["fieldRA", "fieldDec", "altitude", "azimuth"])
        )

    def test_prenight_coordinate_wrapping(self):
        summary = pd.DataFrame(
            {
                "Total": [1],
                "science": [1],
                "median FWHM": [1.0],
                "visits/hour": [1.0],
                "total eff_time/total exp_time": [1.0],
                "teff/night duration": [1.0],
                "science targets": ["COSMOS"],
                "first_visit_decl": [-45.67],
                "first_visit_alt": [60.12],
            },
            index=[20250620],
        )
        for value, expected in [
            (359.996, "0.00"),
            (360.0, "0.00"),
            (721.234, "1.23"),
            (-1.234, "358.77"),
            (-0.004, "0.00"),
            (123.456, "123.46"),
        ]:
            with self.subTest(value=value):
                summary["first_visit_ra"] = value
                summary["first_visit_az"] = value
                original = summary.copy(deep=True)
                description = schedview.reports._format_summary_desc(
                    summary,
                    20250620,
                    "prenight",
                    "lsstcam",
                    None,
                    schedview.reports.RSS_PRENIGHT_DESC_FORMAT,
                )
                assert (
                    f"First simulated visit: RA={expected} deg, decl=-45.67 deg, "
                    f"alt=60.12 deg, az={expected} deg;"
                ) in description.splitlines()
                pd.testing.assert_frame_equal(summary, original)

    def test_prenight_missing_first_visit_coordinates(self):
        visits = pd.DataFrame(
            {
                "dayObs": [20250620, 20250620],
                "observationId": [0, 1],
                "seeingFwhmGeom": [1.0, 1.0],
                "t_eff": [30.0, 30.0],
                "visitExposureTime": [30.0, 30.0],
                "band": ["r", "r"],
                "science_program": ["BLOCK-365"] * 2,
                "target_name": ["COSMOS"] * 2,
                "observationStartMJD": [60846.1, 60846.2],
                "fieldRA": [np.nan, 123.45],
                "fieldDec": [-45.67, -34.56],
                "altitude": [np.inf, 60.12],
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        for missing_all in (False, True):
            with self.subTest(missing_all=missing_all):
                supplied = visits.drop(columns=["fieldDec"]) if missing_all else visits
                root = schedview.reports.make_report_rss_feed(
                    reports, max_days=99999, prenight_visits=supplied
                ).getroot()
                for item in root.iterfind("channel/item"):
                    if item.findtext("category") != "lsstcam_prenight":
                        continue
                    description = item.findtext("description") or ""
                    if item.findtext("title").endswith("2025-06-21"):
                        assert description == ""
                    elif missing_all:
                        assert "Simulated (science) visits: 2" in description
                        assert "First simulated visit:" not in description
                    else:
                        assert (
                            "First simulated visit: RA=unavailable, decl=-45.67 deg, "
                            "alt=unavailable, az=unavailable;"
                        ) in description.splitlines()

    def test_make_report_rss_feed_prenight_blank_when_no_visits(self):
        rng = np.random.default_rng(0)
        n = 40
        # dayObs that do NOT match any test report night (2025-06-20/21).
        dayobs = np.array([20250101] * n)
        prenight_visits = pd.DataFrame(
            {
                "dayObs": dayobs,
                "observationId": np.arange(n),
                "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n),
                "t_eff": rng.uniform(20.0, 40.0, size=n),
                "visitExposureTime": rng.uniform(25.0, 35.0, size=n),
                "band": rng.choice(list("ugrizy"), size=n),
                "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
                "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        rss_tree = schedview.reports.make_report_rss_feed(
            reports, fname=None, max_days=99999, prenight_visits=prenight_visits
        )
        root = rss_tree.getroot()
        # Prenight items with no matching simulation visits get a completely
        # blank description (no "No visits on this night" fallback).
        for item in root.iterfind("channel/item"):
            category = item.findtext("category") or ""
            if category == "lsstcam_prenight":
                assert (item.findtext("description") or "") == ""

    def test_make_report_rss_feed_eff_time_breakdown(self):
        import re

        rng = np.random.default_rng(0)
        n = 40
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
                "eff_time_psf_sigma_scale_median": rng.uniform(0.3, 1.0, size=n),
                "eff_time_zero_point_scale_median": rng.uniform(0.5, 1.0, size=n),
                "eff_time_sky_bg_scale_median": rng.uniform(0.4, 1.0, size=n),
            }
        )
        reports = schedview.reports.find_reports(self.temp_dir.name)
        rss_tree = schedview.reports.make_report_rss_feed(
            reports, fname=None, max_days=99999, visits=visits, science_programs=("BLOCK-365",)
        )
        descriptions = [d.text or "" for d in rss_tree.getroot().iterfind("channel/item/description")]
        joined = "\n".join(descriptions)
        # The breakdown must appear in the format
        # [X PSF, Y transparency, Z sky background]
        assert re.search(r"\[\d+\.\d+ PSF, \d+\.\d+ transparency, \d+\.\d+ sky background\]", joined)

    def test_make_report_rss_feed_no_breakdown_without_columns(self):
        rng = np.random.default_rng(0)
        n = 40
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
        # The breakdown must NOT appear when the columns are absent
        assert "[" not in joined or "PSF" not in joined

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
