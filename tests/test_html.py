import re
import unittest

import matplotlib.pyplot as plt
import pandas as pd

import schedview
import schedview.plot.html


class TestConvertToHtml(unittest.TestCase):
    """Tests for convert_to_html function."""

    def test_with_string_content(self):
        """Test convert_to_html with string content."""
        content = "<p>This is a paragraph.</p>"
        result = schedview.plot.html.convert_to_html(content, collapsed=False)
        self.assertIn(content, result)

    def test_with_string_content_collapsed_false(self):
        """Test convert_to_html with string content and collapsed=False."""
        content = "<p>This is a paragraph.</p>"
        result = schedview.plot.html.convert_to_html(content, collapsed=False)
        self.assertIn(content, result)
        self.assertNotIn("<details>", result)
        self.assertNotIn("<summary>", result)

    def test_with_string_content_and_title(self):
        """Test convert_to_html with string content and a title."""
        content = "<p>This is a paragraph.</p>"
        title = "Test Title"
        result = schedview.plot.html.convert_to_html(content, title=title)
        self.assertIn(title, result)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)

    def test_with_series(self):
        """Test convert_to_html with pandas Series."""
        series = pd.Series({"key1": "value1", "key2": "value2"}, name="values")
        result = schedview.plot.html.convert_to_html(series, collapsed=False)
        self.assertIn("key1", result)
        self.assertIn("value1", result)
        self.assertIn("<table", result)

    def test_with_dataframe(self):
        """Test convert_to_html with pandas DataFrame."""
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        result = schedview.plot.html.convert_to_html(df, collapsed=False)
        self.assertIn("col1", result)
        self.assertIn("col2", result)
        self.assertIn("<table", result)

    def test_with_figure(self):
        """Test convert_to_html with matplotlib Figure."""
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 2, 3])
        result = schedview.plot.html.convert_to_html(fig, collapsed=False)
        # Check that result contains image-related HTML (either img or svg)
        self.assertTrue("<img" in result or "<svg" in result)
        plt.close(fig)

    def test_with_styler(self):
        """Test convert_to_html with pandas Styler."""
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        styler = df.style.highlight_max(axis=0)
        result = schedview.plot.html.convert_to_html(styler, collapsed=False)
        self.assertIn("col1", result)
        self.assertIn("col2", result)

    def test_collapsed_true_without_title_raises(self):
        """Test that collapsed=True without title raises ValueError."""
        content = "some content"
        with self.assertRaises(ValueError):
            schedview.plot.html.convert_to_html(content, collapsed=True)

    def test_collapsed_true_with_title(self):
        """Test collapsed=True with title."""
        content = "<p>content</p>"
        title = "My Title"
        result = schedview.plot.html.convert_to_html(content, title=title, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn(title, result)

    def test_collapsed_false_no_title(self):
        """Test collapsed=False without title returns raw content."""
        content = "<p>raw content</p>"
        result = schedview.plot.html.convert_to_html(content, collapsed=False)
        self.assertIn(content, result)
        self.assertNotIn("<details>", result)

    def test_collapsed_false_with_title(self):
        """Test collapsed=False with title uses heading."""
        content = "<p>content</p>"
        title = "Section Title"
        result = schedview.plot.html.convert_to_html(content, title=title, collapsed=False)
        self.assertIn("<h3>", result)
        self.assertIn(title, result)
        self.assertIn(content, result)

    def test_heading_level_1(self):
        """Test heading level 1."""
        content = "<p>content</p>"
        title = "Title"
        result = schedview.plot.html.convert_to_html(content, title=title, heading_level=1, collapsed=False)
        self.assertIn("<h1>", result)

    def test_heading_level_6(self):
        """Test heading level 6."""
        content = "<p>content</p>"
        title = "Title"
        result = schedview.plot.html.convert_to_html(content, title=title, heading_level=6, collapsed=False)
        self.assertIn("<h6>", result)

    def test_invalid_heading_level_raises(self):
        """Test that invalid heading level raises AssertionError."""
        content = "<p>content</p>"
        with self.assertRaises(AssertionError):
            schedview.plot.html.convert_to_html(content, heading_level=0)

    def test_custom_pd_context_options(self):
        """Test custom pandas context options."""
        df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        result = schedview.plot.html.convert_to_html(
            df, pd_context_options=("display.width", 200), collapsed=False
        )
        self.assertIn("col1", result)


class TestMarkupMappingWithFormat(unittest.TestCase):
    """Tests for markup_mapping_with_format function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        # Overhead summary data matching compute_overhead_summary output
        self.overhead_summary = {
            "relative_start_time": 15.5,
            "relative_end_time": 25.3,
            "total_time": 8.5,
            "num_exposures": 42,
            "total_exptime": 5.25,
            "mean_gap_time": 45.7,
            "median_gap_time": 42.3,
        }

        # Stat name mapping (keys -> display names)
        self.overhead_stat_name = {
            "relative_start_time": "Open shutter of first exposure",
            "relative_end_time": "Close shutter of last exposure",
            "total_time": "Total wall clock time",
            "num_exposures": "Number of exposures",
            "total_exptime": "Total open shutter time",
            "mean_gap_time": "Mean gap time",
            "median_gap_time": "Median gap time",
        }

        # Stat string templates (format strings)
        self.overhead_stat_str_template = {
            "relative_start_time": "{:5.2f} minutes after 12 degree evening twilight",
            "relative_end_time": "{:5.2f} minutes before 12 degree morning twilight",
            "total_time": "{:4.2f} hours",
            "num_exposures": "{}",
            "total_exptime": "{:4.2f} hours",
            "mean_gap_time": "{:7.2f} seconds",
            "median_gap_time": "{:7.2f} seconds",
        }

    def test_collapsed_false_basic(self):
        """Test basic functionality with collapsed=False."""
        result = schedview.plot.html.markup_mapping_with_format(
            self.overhead_summary,
            self.overhead_stat_name,
            self.overhead_stat_str_template,
            ["Number of exposures"],
            "Time on sky",
            collapsed=False,
        )
        # Should contain formatted values
        self.assertIn("15.50", result)
        self.assertIn("42", result)
        # Should not contain details/summary wrapper
        self.assertNotIn("<details>", result)
        self.assertNotIn("<summary>", result)

    def test_summary_fields_appear_in_collapsed_summary(self):
        """Test that summary fields appear in the collapsed summary text."""
        summary_fields = ["Number of exposures", "Mean gap time", "Median gap time"]
        result = schedview.plot.html.markup_mapping_with_format(
            self.overhead_summary,
            self.overhead_stat_name,
            self.overhead_stat_str_template,
            summary_fields,
            "Time on sky",
            collapsed=True,
        )
        # Summary fields should be formatted and appear in the summary.
        self.assertTrue(re.search(r"Number of exposures:\s*42", result))
        self.assertTrue(re.search(r"Mean gap time:\s*45\.70 seconds", result))
        self.assertTrue(re.search(r"Median gap time:\s*42\.30 seconds", result))

    def test_format_templates_applied_correctly(self):
        """Test that format templates are applied correctly."""
        result = schedview.plot.html.markup_mapping_with_format(
            self.overhead_summary,
            self.overhead_stat_name,
            self.overhead_stat_str_template,
            ["total_exptime"],
            "Test",
            collapsed=False,
        )
        # Float formatting with {:4.2f} should produce 2 decimal places
        self.assertIn("5.25", result)
        # Integer formatting with {} should work
        self.assertIn("42", result)

    def test_overhead_summary_data(self):
        """Test with realistic overhead summary data."""
        result = schedview.plot.html.markup_overhead_summary(self.overhead_summary, collapsed=False)
        # All overhead statistics should be present
        self.assertIn("Open shutter of first exposure", result)
        self.assertIn("Close shutter of last exposure", result)
        self.assertIn("Total wall clock time", result)
        self.assertIn("Number of exposures", result)
        self.assertIn("Total open shutter time", result)
        self.assertIn("Mean gap time", result)
        self.assertIn("Median gap time", result)

    def test_collapsed_false_no_title(self):
        """Test collapsed=False with empty title."""
        result = schedview.plot.html.markup_mapping_with_format(
            self.overhead_summary,
            self.overhead_stat_name,
            self.overhead_stat_str_template,
            ["Number of exposures"],
            "",
            collapsed=False,
        )
        # Should contain formatted values
        self.assertIn("15.50", result)
        self.assertIn("42", result)
        # Should not contain details/summary wrapper
        self.assertNotIn("<details>", result)
        self.assertNotIn("<summary>", result)


class TestMarkupSimIndexInfo(unittest.TestCase):
    """Tests for markup_sim_index_info function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        self.sim_index_info = pd.Series(
            {
                "visitseq_uuid": "abc-123-def",
                "sim_creation_day_obs": "2024-08-15",
                "daily_id": 1001,
                "visitseq_label": "baseline_v2.0_10yrs",
                "creation_time": "2024-08-15T12:00:00",
                "telescope": "LSST",
                "visitseq_url": "https://example.com/visitseq",
                "config_url": "https://example.com/config",
                "tags": "baseline,10yrs",
            }
        )
        self.sim_index_info.files = {
            "rewards": "https://example.com/rewards.h5",
            "scheduler_pickle": "https://example.com/scheduler.pickle",
        }

    def test_collapsed_with_title(self):
        """Test markup_sim_index_info with collapsed=True."""
        result = schedview.plot.html.markup_sim_index_info(self.sim_index_info, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("baseline_v2.0_10yrs", result)
        self.assertIn("LSST", result)
        self.assertIn("abc-123-def", result)
        self.assertIn("2024-08-15", result)


class TestMarkupAdditionalSimFiles(unittest.TestCase):
    """Tests for markup_additional_sim_files function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        self.sim_index_info = pd.Series(
            {
                "visitseq_uuid": "abc-123-def",
                "sim_creation_day_obs": "2024-08-15",
            }
        )
        self.sim_index_info.files = {
            "rewards": "https://example.com/rewards.h5",
            "scheduler_pickle": "https://example.com/scheduler.pickle",
        }

    def test_collapsed_with_files(self):
        """Test markup_additional_sim_files with collapsed=True."""
        result = schedview.plot.html.markup_additional_sim_files(self.sim_index_info, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("Additional files available", result)
        self.assertIn("rewards", result)
        self.assertIn("scheduler_pickle", result)
        self.assertIn("https://example.com/rewards.h5", result)


class TestMarkupSimComments(unittest.TestCase):
    """Tests for markup_sim_comments function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        self.sim_info = pd.Series(
            {
                "visitseq_uuid": "abc-123-def",
                "sim_creation_day_obs": "2024-08-15",
            }
        )
        self.sim_info.comments = {
            "2024-08-15T12:00:00": "First comment",
            "2024-08-15T13:00:00": "Second comment",
        }

    def test_collapsed_with_comments(self):
        """Test markup_sim_comments with collapsed=True."""
        result = schedview.plot.html.markup_sim_comments(self.sim_info, collapsed=True)
        # Should contain details/summary wrapper
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("Comments recorded in the simulation metadata database", result)
        self.assertIn("First comment", result)
        self.assertIn("Second comment", result)


class TestMarkupNightEvents(unittest.TestCase):
    """Tests for markup_night_events function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        self.night_events = pd.DataFrame(
            {
                "UTC": [
                    "2024-08-15T05:30:00",
                    "2024-08-15T18:30:00",
                    "2024-08-15T06:30:00",
                    "2024-08-15T17:30:00",
                    "2024-08-15T12:00:00",
                ]
            },
            index=["sunset", "sunrise", "sun_n12_setting", "sun_n12_rising", "night_middle"],
        )
        # Convert strings to datetime objects
        self.night_events["UTC"] = pd.to_datetime(self.night_events["UTC"])

    def test_collapsed_with_title(self):
        """Test markup_night_events with collapsed=True."""
        result = schedview.plot.html.markup_night_events(self.night_events, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("Sunset:", result)
        self.assertIn("Sunrise:", result)


class TestMarkupSunMoonPositions(unittest.TestCase):
    """Tests for markup_sun_moon_positions function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        import numpy as np

        # Position data in radians
        self.sun_moon_positions = {
            "sun_RA": np.radians(100.0),
            "sun_dec": np.radians(20.0),
            "sun_alt": np.radians(30.0),
            "sun_az": np.radians(180.0),
            "moon_RA": np.radians(150.0),
            "moon_dec": np.radians(-10.0),
            "moon_alt": np.radians(45.0),
            "moon_az": np.radians(270.0),
            "moon_phase": 50.0,
        }

    def test_collapsed_with_title(self):
        """Test markup_sun_moon_positions with collapsed=True."""
        result = schedview.plot.html.markup_sun_moon_positions(self.sun_moon_positions, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("Sun", result)
        self.assertIn("Moon", result)


class TestMarkupSurveyVisitSummary(unittest.TestCase):
    """Tests for markup_survey_visit_summary function."""

    def setUp(self):
        """Create test data matching real usage patterns."""
        self.survey_visit_summary = {
            "n12_night_time": 10.5,
            "n_survey_visits": 42,
            "n_pairs_started": 15,
            "n_pairs_finished": 12,
            "ddfs_observed": 5,
            "too_observed": 3,
        }

    def test_collapsed_with_title(self):
        """Test markup_survey_visit_summary with collapsed=True."""
        result = schedview.plot.html.markup_survey_visit_summary(self.survey_visit_summary, collapsed=True)
        self.assertIn("<details>", result)
        self.assertIn("<summary>", result)
        self.assertIn("Number of survey visits", result)
        self.assertIn("DDFs Observed", result)
        self.assertIn("ToOs Observed", result)
        self.assertIn("Time between 12 degree evening and morning twilights", result)
        self.assertIn("Number of survey visits in night", result)


if __name__ == "__main__":
    unittest.main()
