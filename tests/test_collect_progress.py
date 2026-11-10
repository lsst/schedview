"""Readable unittest scenarios for loading and validating SQLite summaries."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from schedview.collect.progress import load_summary_metrics, validate_summary_metrics


class TestCollectProgress(unittest.TestCase):
    """Load real databases, then check the records callers can work with."""

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def database(self, *rows, name="results.db"):
        """Create a MAF database with overrides for a default measurement."""
        path = self.directory / name
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.executescript(
                "CREATE TABLE metrics (metric_id INTEGER PRIMARY KEY, run_name VARCHAR, "
                "metric_name VARCHAR, slicer_name VARCHAR, sql_constraint VARCHAR, "
                "metric_info_label VARCHAR);"
                "CREATE TABLE summarystats (stat_id INTEGER PRIMARY KEY, metric_id INTEGER, "
                "summary_name VARCHAR, summary_value FLOAT);"
            )
            for index, overrides in enumerate(rows, start=1):
                row = dict(
                    metric_id=index,
                    stat_id=index,
                    run_name="chimera_20260228",
                    metric_name="Depth",
                    slicer_name="UniSlicer",
                    sql_constraint="",
                    metric_info_label="chimera_g",
                    summary_metric="Mean",
                    summary_value=1.5,
                )
                row.update(overrides)
                connection.execute(
                    "INSERT INTO metrics VALUES (:metric_id, :run_name, :metric_name, :slicer_name, "
                    ":sql_constraint, :metric_info_label)",
                    row,
                )
                connection.execute(
                    "INSERT INTO summarystats VALUES (:stat_id, :metric_id, :summary_metric, :summary_value)",
                    row,
                )
        return path

    def test_load_sources_labels_and_calendar_date(self):
        """Keep supported values and labels while skipping unrelated runs."""
        path = self.database(
            {"run_name": "chimera_20280229", "summary_value": 2.5},
            {"run_name": "consdb_20280301", "metric_info_label": "consdb_r", "summary_value": 3.5},
            {"run_name": "baseline_20280301", "metric_info_label": "foo", "summary_value": 4.5},
            {"run_name": "unrelated", "metric_name": None},
        )
        with self.assertWarnsRegex(UserWarning, "excluded 1"):
            result = load_summary_metrics(path)
        by_source = result.set_index("visit_source")
        self.assertCountEqual(by_source.index, ["chimera", "consdb", "baseline"])
        self.assertEqual(by_source.band.to_dict(), {"chimera": "g", "consdb": "r", "baseline": "all"})
        self.assertEqual(
            by_source.metric_info_label.to_dict(),
            {"chimera": "chimera_g", "consdb": "consdb_r", "baseline": "foo"},
        )
        self.assertEqual(by_source.summary_value.to_dict(), {"chimera": 2.5, "consdb": 3.5, "baseline": 4.5})
        self.assertEqual(by_source.loc["chimera", "date"], pd.Timestamp("2028-02-29"))

    def test_reruns_keep_latest_provenance_but_cannot_change_the_value(self):
        """Keep the highest stat ID for equal reruns; reject conflicts."""
        equal_reruns = self.database(
            {"stat_id": 20, "summary_value": 1.5},
            {"stat_id": 5, "summary_value": 1.5},
        )
        result = load_summary_metrics(equal_reruns)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0].stat_id, 20)
        self.assertEqual(result.iloc[0].metric_id, 1)
        self.assertEqual(result.iloc[0].summary_value, 1.5)

        conflicting = self.database(
            {"stat_id": 20, "summary_value": 1.5},
            {"stat_id": 5, "summary_value": 2.5},
            name="conflicting.db",
        )
        with self.assertRaisesRegex(ValueError, "conflicting summary_value"):
            load_summary_metrics(conflicting)

    def test_validate_filtered_records_and_equal_duplicates_without_mutating(self):
        """Accept caller metadata and require opt-in for equal duplicates."""
        frame = load_summary_metrics(self.database({}, {"run_name": "chimera_20260301"}))
        filtered = frame.iloc[[1]].copy()
        filtered.index = ["arbitrary"]
        filtered["extra"] = "untouched"
        original = filtered.copy(deep=True)
        self.assertIsNone(validate_summary_metrics(filtered))
        pd.testing.assert_frame_equal(filtered, original)

        duplicates = pd.concat([frame, frame.iloc[[0]]])
        original = duplicates.copy(deep=True)
        with self.assertRaisesRegex(ValueError, "duplicate summary record"):
            validate_summary_metrics(duplicates)
        self.assertIsNone(validate_summary_metrics(duplicates, allow_duplicates=True))
        pd.testing.assert_frame_equal(duplicates, original)

    def test_sequence_invariants_across_dates_and_sources(self):
        """A shared label cannot join measurements from different slicers."""
        path = self.database(
            {"run_name": "chimera_20260228", "metric_info_label": "foo_g", "slicer_name": "UniSlicer"},
            {"run_name": "consdb_20260301", "metric_info_label": "foo_g", "slicer_name": "HealpixSlicer"},
        )
        with self.assertRaisesRegex(ValueError, "multiple slicer_name"):
            load_summary_metrics(path)

    def test_input_errors_identify_the_source_without_creating_a_database(self):
        """Leave missing paths absent and report impossible dates by run."""
        missing = self.directory / "absent.db"
        with self.assertRaisesRegex(ValueError, "absent.db"):
            load_summary_metrics(missing)
        self.assertFalse(missing.exists())

        run = "chimera_20260230"
        invalid = self.database({"run_name": run})
        with self.assertRaisesRegex(ValueError, run):
            load_summary_metrics(invalid)


if __name__ == "__main__":
    unittest.main()
