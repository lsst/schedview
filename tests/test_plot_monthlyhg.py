import unittest
import datetime
from unittest.mock import MagicMock
from matplotlib import pyplot as plt
from xml.etree import ElementTree as ET

from schedview.plot.monthlyhg import plot_collapsed_monthly_hourglass_metric


class TestPlotCollapsedMonthlyHourglassMetric(unittest.TestCase):

    def setUp(self):
        """Create a mock MetricBundle to support testing without maf."""
        self.bundle = MagicMock()
        self.bundle.plot_dict = {}
        self.bundle.plot_funcs = []
        self.bundle.plot.return_value = {"dummy": plt.figure()}

    def test_html_output_for_two_months(self):
        """Run the function over a two‑month span and sanity check result."""

        first_date = datetime.date.fromisoformat("2027-01-01")
        last_date = datetime.date.fromisoformat("2027-02-01")

        result = plot_collapsed_monthly_hourglass_metric(
            metric_bundle=self.bundle,
            name="TestMetric",
            first_date=first_date,
            last_date=last_date,
        )

        assert isinstance(result, str)
        assert len(result) > 0

        # Parse the HTML using ElementTree
        root = ET.fromstring(f"<html>{result}</html>")

        # Check we have all the children we expect
        details_elements = root.findall(".//details")
        assert len(details_elements) == 2

        summary_elements = root.findall(".//summary")
        assert len(summary_elements) == 2

        img_elements = root.findall(".//img")
        assert len(img_elements) == 2

        # Verify that each img has a src attribute with base64 data
        for img in img_elements:
            src = img.get("src", "")
            assert src.startswith("data:image/png;base64,")


if __name__ == "__main__":
    unittest.main()
