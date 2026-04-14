import datetime
import unittest
from collections import namedtuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy.time import Time

import schedview
import schedview.compute.astro
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


if __name__ == "__main__":
    unittest.main()
