"""Tests for the MAF summary metric plotter module."""

import json
import os
import sqlite3
from datetime import date
from tempfile import TemporaryDirectory
from unittest import TestCase

import bokeh.models
import bokeh.plotting
import pandas as pd

from schedview.collect.maf_summary import load_maf_summary
from schedview.plot.maf_summary import (
    _build_cascading_maps,
    _build_data_dict,
    make_metric_selector_plot,
    save_metric_data_json,
)


def _create_fixture_db(db_path: str) -> None:
    """Create a minimal ResultsDb fixture for testing."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE metrics (
            metric_id INTEGER PRIMARY KEY,
            run_name TEXT,
            metric_name TEXT,
            slicer_name TEXT,
            metric_info_label TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE summarystats (
            stat_id INTEGER PRIMARY KEY,
            metric_id INTEGER,
            summary_name TEXT,
            summary_value REAL
        )
        """
    )
    # Insert sample metric rows for two chimera runs
    conn.execute(
        "INSERT INTO metrics VALUES"
        " (1, 'chimera_20251031', 'fO', 'HealpixSlicer', '')"
    )
    conn.execute(
        "INSERT INTO metrics VALUES"
        " (2, 'chimera_20251130', 'fO', 'HealpixSlicer', '')"
    )
    conn.execute(
        "INSERT INTO metrics VALUES"
        " (3, 'chimera_20251031', 'fO', 'HealpixSlicer',"
        " 'g band')"
    )
    conn.execute(
        "INSERT INTO metrics VALUES"
        " (4, 'chimera_20251130', 'fO', 'HealpixSlicer',"
        " 'g band')"
    )
    # Insert summary stats
    conn.execute(
        "INSERT INTO summarystats VALUES (1, 1, 'fOArea', 100.0)"
    )
    conn.execute(
        "INSERT INTO summarystats VALUES (2, 2, 'fOArea', 150.0)"
    )
    conn.execute(
        "INSERT INTO summarystats VALUES (3, 3, 'fOArea', 200.0)"
    )
    conn.execute(
        "INSERT INTO summarystats VALUES (4, 4, 'fOArea', 250.0)"
    )
    conn.commit()
    conn.close()


class TestBuildDataDict(TestCase):
    """Tests for _build_data_dict."""

    def test_build_data_dict(self):
        """Test that _build_data_dict creates correct data structure."""
        summary_df = pd.DataFrame(
            {
                "run_name": [
                    "chimera_20251031",
                    "chimera_20251031",
                ],
                "metric_name": ["fO", "fO"],
                "slicer_name": ["HealpixSlicer", "HealpixSlicer"],
                "metric_info_label": ["", "g band"],
                "summary_metric": ["fOArea", "fOArea"],
                "summary_value": [100.0, 200.0],
                "transition_dayobs": [20251031, 20251031],
                "transition_date": [
                    date(2025, 10, 31),
                    date(2025, 10, 31),
                ],
            }
        )

        data_dict = _build_data_dict(summary_df)

        # Check keys are correctly formatted
        self.assertIn("fO|<none>|fOArea", data_dict)
        self.assertIn("fO|g band|fOArea", data_dict)

        # Check data structure
        entry = data_dict["fO|<none>|fOArea"]
        self.assertIn("transition_date", entry)
        self.assertIn("transition_date_labels", entry)
        self.assertIn("summary_value", entry)
        self.assertIn("run_name", entry)

    def test_build_data_dict_empty_string_info_label(self):
        """Test handling of empty string metric_info_label."""
        summary_df = pd.DataFrame(
            {
                "run_name": ["chimera_20251031"],
                "metric_name": ["fO"],
                "slicer_name": ["HealpixSlicer"],
                "metric_info_label": [""],
                "summary_metric": ["fOArea"],
                "summary_value": [100.0],
                "transition_dayobs": [20251031],
                "transition_date": [date(2025, 10, 31)],
            }
        )

        data_dict = _build_data_dict(summary_df)

        # Empty string info_label should become '<none>'
        self.assertIn("fO|<none>|fOArea", data_dict)


class TestBuildCascadingMaps(TestCase):
    """Tests for _build_cascading_maps."""

    def test_build_cascading_maps(self):
        """Test cascading dropdown mappings."""
        unique_metrics = pd.DataFrame(
            {
                "run_name": [
                    "chimera_20251031",
                    "chimera_20251031",
                    "chimera_20251031",
                ],
                "metric_name": ["fO", "fO", "SNR"],
                "slicer_name": ["HealpixSlicer"] * 3,
                "metric_info_label": ["", "g band", ""],
                "summary_metric": ["fOArea", "fOArea", "SNR Median"],
            }
        )

        metric_to_info, metric_info_to_summary = (
            _build_cascading_maps(unique_metrics)
        )

        # Check metric_to_info
        self.assertIn("fO", metric_to_info)
        self.assertIn("SNR", metric_to_info)
        self.assertEqual(len(metric_to_info["fO"]), 2)
        self.assertIn("<none>", metric_to_info["fO"])
        self.assertIn("g band", metric_to_info["fO"])

        # Check metric_info_to_summary
        self.assertIn("fO|<none>", metric_info_to_summary)
        self.assertIn("fO|g band", metric_info_to_summary)
        self.assertEqual(
            metric_info_to_summary["fO|<none>"], ["fOArea"]
        )
        self.assertEqual(
            metric_info_to_summary["fO|g band"], ["fOArea"]
        )
        self.assertEqual(
            metric_info_to_summary["SNR|<none>"], ["SNR Median"]
        )


class TestMakeMetricSelectorPlot(TestCase):
    """Tests for make_metric_selector_plot."""

    def setUp(self):
        """Set up test data."""
        self.summary_df = pd.DataFrame(
            {
                "run_name": [
                    "chimera_20251031",
                    "chimera_20251130",
                ],
                "metric_name": ["fO", "fO"],
                "slicer_name": ["HealpixSlicer", "HealpixSlicer"],
                "metric_info_label": ["", ""],
                "summary_metric": ["fOArea", "fOArea"],
                "summary_value": [100.0, 150.0],
                "transition_dayobs": [20251031, 20251130],
                "transition_date": [
                    date(2025, 10, 31),
                    date(2025, 11, 30),
                ],
            }
        )
        self.unique_metrics = self.summary_df.drop_duplicates(
            subset=[
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        ).sort_values(
            [
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        )

    def test_basic_plot_creation(self):
        """Test basic plot creation."""
        plot = make_metric_selector_plot(
            self.summary_df, self.unique_metrics
        )

        # Check plot type
        self.assertIsInstance(plot, bokeh.layouts.Column)

        # Check children (selectors row + plot = 2, no heading)
        self.assertEqual(len(plot.children), 2)

        # Check widgets exist
        selectors_row = plot.children[0]
        self.assertIsInstance(selectors_row, bokeh.layouts.Row)
        self.assertEqual(len(selectors_row.children), 3)

        # Check metric name selector
        metric_selector = selectors_row.children[0]
        self.assertIsInstance(metric_selector, bokeh.models.Select)
        self.assertEqual(metric_selector.value, "fO")
        self.assertEqual(metric_selector.options, ["fO"])

    def test_plot_with_build_date(self):
        """Test plot with custom build date."""
        plot = make_metric_selector_plot(
            self.summary_df,
            self.unique_metrics,
            build_date="2026-07-07",
        )

        # heading + selectors + plot = 3 children
        self.assertEqual(len(plot.children), 3)
        heading = plot.children[0]
        self.assertIsInstance(heading, bokeh.models.PreText)
        self.assertIn("2026-07-07", heading.text)

    def test_plot_with_external_json_url(self):
        """Test plot with external JSON URL."""
        plot = make_metric_selector_plot(
            self.summary_df,
            self.unique_metrics,
            data_json_url="data.json",
        )

        self.assertIsInstance(plot, bokeh.layouts.Column)
        # selectors + plot = 2 children (no build_date heading)
        self.assertEqual(len(plot.children), 2)


class TestSaveMetricDataJson(TestCase):
    """Tests for save_metric_data_json."""

    def test_save_metric_data_json(self):
        """Test JSON data file creation."""
        summary_df = pd.DataFrame(
            {
                "run_name": ["chimera_20251031"],
                "metric_name": ["fO"],
                "slicer_name": ["HealpixSlicer"],
                "metric_info_label": [""],
                "summary_metric": ["fOArea"],
                "summary_value": [100.0],
                "transition_dayobs": [20251031],
                "transition_date": [date(2025, 10, 31)],
            }
        )
        unique_metrics = summary_df.drop_duplicates(
            subset=[
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        ).sort_values(
            [
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        )

        with TemporaryDirectory() as tmpdir:
            json_path = f"{tmpdir}/test_data.json"
            save_metric_data_json(
                summary_df, unique_metrics, json_path
            )

            with open(json_path, "r") as f:
                data = json.load(f)

            self.assertIn("data_dict", data)
            self.assertIn("metric_to_info", data)
            self.assertIn("metric_info_to_summary", data)

    def test_save_metric_data_json_empty_string_handling(self):
        """Test empty string handling in JSON output."""
        summary_df = pd.DataFrame(
            {
                "run_name": ["chimera_20251031"],
                "metric_name": ["fO"],
                "slicer_name": ["HealpixSlicer"],
                "metric_info_label": [""],
                "summary_metric": ["fOArea"],
                "summary_value": [100.0],
                "transition_dayobs": [20251031],
                "transition_date": [date(2025, 10, 31)],
            }
        )
        unique_metrics = summary_df.drop_duplicates(
            subset=[
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        ).sort_values(
            [
                "metric_name",
                "slicer_name",
                "metric_info_label",
                "summary_metric",
            ]
        )

        with TemporaryDirectory() as tmpdir:
            json_path = f"{tmpdir}/test_data.json"
            save_metric_data_json(
                summary_df, unique_metrics, json_path
            )

            with open(json_path, "r") as f:
                data = json.load(f)

            self.assertIn("fO|<none>|fOArea", data["data_dict"])


class TestLoadMafSummary(TestCase):
    """Tests for load_maf_summary defensive parsing."""

    def setUp(self):
        """Create a fixture database."""
        self.tmpdir = TemporaryDirectory()
        self.db_path = os.path.join(
            self.tmpdir.name, "resultsDb_sqlite.db"
        )
        _create_fixture_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_basic(self):
        """Test basic load from fixture database."""
        summary_df, unique_metrics = load_maf_summary(self.db_path)

        self.assertGreater(len(summary_df), 0)
        self.assertGreater(len(unique_metrics), 0)
        self.assertIn("transition_date", summary_df.columns)
        self.assertIn("transition_dayobs", summary_df.columns)

    def test_load_malformed_run_names(self):
        """Test that malformed run names are dropped gracefully."""
        # Add a row with a malformed run_name (no date suffix)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO metrics VALUES"
            " (10, 'badname', 'fO', 'HealpixSlicer', '')"
        )
        conn.execute(
            "INSERT INTO summarystats VALUES"
            " (10, 10, 'fOArea', 999.0)"
        )
        conn.commit()
        conn.close()

        # Should still succeed, dropping the bad row
        summary_df, unique_metrics = load_maf_summary(
            self.db_path, run_name_pattern="%"
        )

        # The good rows should still be present
        self.assertGreater(len(summary_df), 0)
        # The bad run_name should not appear
        self.assertNotIn("badname", summary_df["run_name"].values)

    def test_load_all_malformed_raises(self):
        """Test ValueError when no rows have parseable dates."""
        # Create a DB with only bad run names
        tmpdir = TemporaryDirectory()
        db_path = os.path.join(tmpdir.name, "bad.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE metrics (
                metric_id INTEGER PRIMARY KEY,
                run_name TEXT,
                metric_name TEXT,
                slicer_name TEXT,
                metric_info_label TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE summarystats (
                stat_id INTEGER PRIMARY KEY,
                metric_id INTEGER,
                summary_name TEXT,
                summary_value REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO metrics VALUES"
            " (1, 'no_date_here', 'fO', 'Slicer', '')"
        )
        conn.execute(
            "INSERT INTO summarystats VALUES"
            " (1, 1, 'fOArea', 100.0)"
        )
        conn.commit()
        conn.close()

        with self.assertRaises(ValueError):
            load_maf_summary(db_path, run_name_pattern="%")

        tmpdir.cleanup()


class TestIntegration(TestCase):
    """Integration tests for the full workflow."""

    def setUp(self):
        """Create a fixture database for integration testing."""
        self.tmpdir = TemporaryDirectory()
        self.db_path = os.path.join(
            self.tmpdir.name, "resultsDb_sqlite.db"
        )
        _create_fixture_db(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_full_workflow(self):
        """Test the full collect -> plot -> save workflow."""
        summary_df, unique_metrics = load_maf_summary(self.db_path)

        # Verify we got data
        self.assertGreater(len(summary_df), 0)
        self.assertGreater(len(unique_metrics), 0)

        # Create plot
        plot = make_metric_selector_plot(
            summary_df, unique_metrics
        )
        self.assertIsInstance(plot, bokeh.layouts.Column)

        # Save to JSON
        json_path = os.path.join(self.tmpdir.name, "test_data.json")
        save_metric_data_json(
            summary_df, unique_metrics, json_path
        )

        with open(json_path, "r") as f:
            data = json.load(f)

        # Verify JSON has expected structure
        self.assertIn("data_dict", data)
        self.assertIn("metric_to_info", data)
        self.assertIn("metric_info_to_summary", data)
