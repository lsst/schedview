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


if __name__ == "__main__":
    unittest.main()
