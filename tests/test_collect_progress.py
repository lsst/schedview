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

    def test_alternate_reference_replaces_baseline_and_keeps_literal_identity(self):
        """Keep one comparison's identity and reject baseline frames."""
        for tag in ("comparison", "ref.v1_+"):
            with self.subTest(reference_sim_tag=tag):
                path = self.database(
                    {"run_name": f"{tag}_20280229", "metric_info_label": f"{tag}_r"},
                    {"run_name": "consdb_20280301", "metric_info_label": f"{tag}_r"},
                    {"run_name": "chimera_20280301", "metric_info_label": "chimera_g"},
                    {"run_name": "baseline_20260230", "metric_name": None},
                    {"run_name": "baseline_20280301", "metric_info_label": "baseline_r"},
                    {"run_name": f"{tag.upper()}_20280301", "metric_name": None},
                    name=f"{tag}.db",
                )
                with self.assertWarnsRegex(UserWarning, "excluded 3"):
                    frame = load_summary_metrics(path, reference_sim_tag=tag)
                by_source = frame.set_index("visit_source")
                self.assertCountEqual(by_source.index, [tag, "chimera", "consdb"])
                self.assertEqual(by_source.loc[tag, "run_name"], f"{tag}_20280229")
                self.assertEqual(by_source.loc[tag, "metric_info_label"], f"{tag}_r")
                self.assertEqual(by_source.loc[tag, "date"], pd.Timestamp("2028-02-29"))
                self.assertEqual(by_source.band.to_dict(), {tag: "r", "chimera": "g", "consdb": "all"})
                original = frame.copy(deep=True)
                validate_summary_metrics(frame, reference_sim_tag=tag)
                validate_summary_metrics(frame.iloc[[0]], reference_sim_tag=tag)
                validate_summary_metrics(
                    pd.concat([frame, frame]), reference_sim_tag=tag, allow_duplicates=True
                )
                pd.testing.assert_frame_equal(frame, original)
                with self.assertRaisesRegex(ValueError, "Invalid run_name"):
                    validate_summary_metrics(frame)

        baseline = load_summary_metrics(
            self.database(
                {"run_name": "baseline_20280301", "metric_info_label": "baseline_r"}, name="baseline.db"
            )
        )
        with self.assertRaisesRegex(ValueError, "baseline_20280301"):
            validate_summary_metrics(baseline, reference_sim_tag="comparison")

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

        empty = load_summary_metrics(self.database(name="empty.db"))
        for tag in ("", None, 42, "consdb", "chimera"):
            with self.subTest(reference_sim_tag=tag):
                with self.assertRaisesRegex(ValueError, "reference_sim_tag"):
                    load_summary_metrics(invalid, reference_sim_tag=tag)
                with self.assertRaisesRegex(ValueError, "reference_sim_tag"):
                    validate_summary_metrics(empty, reference_sim_tag=tag)


if __name__ == "__main__":
    unittest.main()
