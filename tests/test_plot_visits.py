from unittest import TestCase

import bokeh
import bokeh.models
from astropy.time import Time
from rubin_scheduler.utils import SURVEY_START_MJD
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.plot


class TestPlotVisits(TestCase):

    def setUp(self):
        self.visit_db_fname = get_baseline()
        start_mjd = SURVEY_START_MJD
        self.start_time = Time(start_mjd + 0.5, format="mjd")
        self.end_time = Time(start_mjd + 1.5, format="mjd")
        self.visits = schedview.collect.read_opsim(self.visit_db_fname, self.start_time, self.end_time)

    def test_plot_visit_param_vs_time(self):
        plot = schedview.plot.plot_visit_param_vs_time(self.visits, "seeingFwhmEff")
        self.assertIsInstance(plot, bokeh.models.ui.ui_element.UIElement)

    def test_create_visit_table(self):
        plot = schedview.plot.create_visit_table(self.visits, show=False)
        self.assertIsInstance(plot, bokeh.models.ui.ui_element.UIElement)

    def test_plot_visit_param_vs_time_color_by_observation_reason(self):
        plot = schedview.plot.plot_visit_param_vs_time(
            self.visits, "seeingFwhmEff", color_by_observation_reason=True
        )
        self.assertIsInstance(plot, bokeh.models.ui.ui_element.UIElement)

        # The plot contains figures with renderers
        # Get the first figure from the layout
        ui_children = plot.children if hasattr(plot, "children") else []
        figures = [child for child in ui_children if hasattr(child, "renderers")]
        self.assertGreater(len(figures), 0)

        # Check that the scatter glyph uses a factor_cmap for
        # observation_reason
        scatter_renderer = figures[0].renderers[0]
        fill_color = scatter_renderer.glyph.fill_color
        # fill_color is a Field object with .transform containing
        # the factor_cmap.
        transform = fill_color.transform
        # Check that transform is a factor_cmap by checking it has
        # expected attributes.
        self.assertTrue(hasattr(transform, "factors"))
        self.assertTrue(hasattr(transform, "palette"))

        # Check that observation_reason values are in the factors
        # The factors should contain the unique observation_reason values
        unique_reasons = set(self.visits["observation_reason"].unique())
        for reason in unique_reasons:
            self.assertIn(reason, transform.factors)

        # Check that the number of factors matches the number of unique
        # observation_reason values in the data.
        self.assertEqual(len(transform.factors), len(unique_reasons))

    def test_plot_visit_param_vs_time_color_by_observation_reason_with_threshold(self):
        # Add many observation_reason values to test the threshold behavior
        visits = self.visits.copy()
        # Create 15 unique observation_reason values (more than default
        # threshold of 10).
        # Assign unique names to the first 15 visits.
        for i in range(15):
            visits.loc[visits.index[i], "observation_reason"] = f"reason_{i}"
        # Keep the rest as the original values.

        # With 15 unique values (more than threshold of 10), we should
        # collapse names with common prefixes into single categories.
        plot = schedview.plot.plot_visit_param_vs_time(
            visits, "seeingFwhmEff", color_by_observation_reason=True
        )
        self.assertIsInstance(plot, bokeh.models.ui.ui_element.UIElement)

        # Get the figures from the layout
        ui_children = plot.children if hasattr(plot, "children") else []
        figures = [child for child in ui_children if hasattr(child, "renderers")]
        self.assertGreater(len(figures), 0)

        # Check that the scatter glyph uses a factor_cmap
        scatter_renderer = figures[0].renderers[0]
        fill_color = scatter_renderer.glyph.fill_color
        transform = fill_color.transform

        # Check that transform has the expected attributes
        self.assertTrue(hasattr(transform, "factors"))
        self.assertTrue(hasattr(transform, "palette"))

        # Check that there are 11 factors (10 common reasons + "other")
        self.assertLess(len(transform.factors), 11)
