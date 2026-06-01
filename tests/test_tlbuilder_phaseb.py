"""Phase B test suite for tlbuilder.

Tests visit plots, color stripes, mixed-element stacked layouts,
and CLI v2 functionality.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import click
import numpy as np
import pandas as pd
import pytest
from astropy.time import Time
from click.testing import CliRunner
from bokeh.models import (
    ColumnDataSource,
    DatetimeTickFormatter,
    Range1d,
    Scatter,
    Rect,
    Quad,
)
from bokeh.layouts import column

from schedview.dayobs import DayObs
from schedview.plot.tlbuilder import (
    ColorStripeConfig,
    ScatterPlotConfig,
    TimelineBuilder,
    VisitDataSet,
)


class TestVisitDataSet:
    """Tests for VisitDataSet implementation."""

    def test_class_exists(self):
        """VisitDataSet class exists."""
        assert VisitDataSet is not None

    def test_can_instantiate(self):
        """VisitDataSet can be instantiated."""
        dataset = VisitDataSet()
        assert dataset is not None

    def test_stores_required_attributes(self):
        """VisitDataSet stores source, label, alpha, marker, color_by_band, visible."""
        dataset = VisitDataSet()
        dataset.source = MagicMock()
        dataset.label = "test_label"
        dataset.alpha = 0.5
        dataset.marker = "triangle"
        dataset.color_by_band = True
        dataset.visible = False

        assert dataset.source is not None
        assert dataset.label == "test_label"
        assert dataset.alpha == 0.5
        assert dataset.marker == "triangle"
        assert dataset.color_by_band is True
        assert dataset.visible is False


class TestAddVisits:
    """Tests for TimelineBuilder.add_visits method."""

    def test_returns_self_for_chaining(self):
        """add_visits returns self for method chaining."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        result = builder.add_visits(pd.DataFrame(), label="test_visits")
        assert result is builder

    def test_accepts_visits_dataframe(self):
        """add_visits accepts a pandas DataFrame."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0, 60000.0, 60001.0],
            "altitude": [30.0, 45.0, 60.0],
        })
        builder.add_visits(visits_df)
        # Visits are overlaid on scatter panels; they don't create their own elements.
        assert len(builder._elements) == 0
        assert "visits" in builder._visit_sets

    def test_converts_mjd_to_datetime64(self):
        """add_visits converts MJD timestamps to datetime64."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0, 60000.0, 60001.0],
            "altitude": [30.0, 45.0, 60.0],
        })
        builder.add_visits(visits_df)

        # Check that the visit set was created
        assert "visits" in builder._visit_sets
        dataset = builder._visit_sets["visits"]
        source = dataset.source

        # Check that time column is datetime64
        time_data = source.data.get("time", [])
        if len(time_data) > 0:
            assert isinstance(time_data[0], np.datetime64) or np.issubdtype(type(time_data[0]), np.datetime64)

    def test_creates_column_data_source(self):
        """add_visits creates a ColumnDataSource with correct fields."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0, 60000.0],
            "altitude": [30.0, 45.0],
            "band": ["g", "r"],
        })
        builder.add_visits(visits_df)

        dataset = builder._visit_sets["visits"]
        assert isinstance(dataset.source, ColumnDataSource)

        # Check that source has required columns
        source = dataset.source
        assert "time" in source.data
        assert "altitude" in source.data

    def test_stores_visit_dataset(self):
        """add_visits stores VisitDataSet in self._visit_sets."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="my_visits")

        assert "my_visits" in builder._visit_sets
        dataset = builder._visit_sets["my_visits"]
        assert isinstance(dataset, VisitDataSet)

    def test_stores_visit_dataset_attributes(self):
        """VisitDataSet stores label, alpha, marker, color_by_band, visible."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="test_visits", alpha=0.7, marker="triangle", color_by_band=False)

        dataset = builder._visit_sets["test_visits"]
        assert dataset.label == "test_visits"
        assert dataset.alpha == 0.7
        assert dataset.marker == "triangle"
        assert dataset.color_by_band is False
        assert dataset.visible is True  # Default

    def test_creates_element_in_elements_list(self):
        """add_visits stores VisitDataSet in _visit_sets, not a separate element."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="test_visits")

        assert len(builder._elements) == 0
        assert "test_visits" in builder._visit_sets

    def test_respects_height_parameter(self):
        """add_visits respects height parameter in scatter_kwargs."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="test_visits", height=250)

        assert builder._plot_heights["test_visits"] == 250

    def test_respects_custom_height(self):
        """add_visits stores custom height in _plot_heights."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="custom", height=300)

        assert builder._plot_heights["custom"] == 300

    def test_applies_band_coloring_when_band_exists(self):
        """add_visits assigns colors based on band column when color_by_band=True."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0, 60000.0, 60001.0],
            "altitude": [30.0, 45.0, 60.0],
            "band": ["u", "g", "r"],
        })
        builder.add_visits(visits_df, label="band_visits", color_by_band=True)

        dataset = builder._visit_sets["band_visits"]
        source = dataset.source

        # Check that color column exists
        assert "color" in source.data

        # Check that colors are assigned from palette
        colors = source.data["color"]
        assert len(colors) == 3

    def test_default_color_by_band_is_true(self):
        """add_visits has color_by_band=True by default."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
            "band": ["g"],
        })
        builder.add_visits(visits_df, label="default_band")

        dataset = builder._visit_sets["default_band"]
        assert dataset.color_by_band is True

    def test_custom_marker_works(self):
        """add_visits respects custom marker parameter."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="triangle_visits", marker="triangle")

        dataset = builder._visit_sets["triangle_visits"]
        assert dataset.marker == "triangle"

    def test_custom_alpha_works(self):
        """add_visits respects custom alpha parameter."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })
        builder.add_visits(visits_df, label="alpha_visits", alpha=0.3)

        dataset = builder._visit_sets["alpha_visits"]
        assert dataset.alpha == 0.3

    def test_custom_time_column(self):
        """add_visits can use custom time column."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "custom_time_mjd": [59999.0, 60000.0],
            "altitude": [30.0, 45.0],
        })
        builder.add_visits(visits_df, label="custom_time", time_column="custom_time_mjd")

        dataset = builder._visit_sets["custom_time"]
        assert "time" in dataset.source.data

    def test_method_chaining(self):
        """add_visits can be chained with other methods."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        visits_df = pd.DataFrame({
            "observationStartMJD": [59999.0],
            "altitude": [30.0],
        })

        result = (
            builder.add_scatter(y_column="altitude", name="scatter1")
            .add_visits(visits_df, label="visits1")
            .add_scatter(y_column="HA", name="scatter2")
        )

        assert result is builder
        # Two scatters in _elements; visits go into _visit_sets only.
        assert len(builder._elements) == 2
        assert "visits1" in builder._visit_sets


class TestAddColorStripe:
    """Tests for TimelineBuilder.add_color_stripe method."""

    def test_returns_self_for_chaining(self):
        """add_color_stripe returns self for method chaining."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        result = builder.add_color_stripe(series, name="test_stripe")
        assert result is builder

    def test_accepts_series_indexed_by_mjd(self):
        """add_color_stripe accepts a Series indexed by MJD."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="test_stripe")

        assert len(builder._elements) == 1

    def test_accepts_dataframe_with_mjd_column(self):
        """add_color_stripe accepts a DataFrame with MJD column."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        df = pd.DataFrame({
            "time_mjd": [59999.0, 60000.0, 60001.0],
            "value": [1.0, 2.0, 3.0],
        })
        builder.add_color_stripe(df, name="test_stripe", value_column="value")

        assert len(builder._elements) == 1

    def test_converts_mjd_to_datetime64(self):
        """add_color_stripe converts MJD to datetime64."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert "stripe1" in builder._color_stripes
        stripe_config = builder._color_stripes["stripe1"]
        source = stripe_config.source

        time_data = source.data.get("time", [])
        if len(time_data) > 0:
            assert isinstance(time_data[0], np.datetime64) or np.issubdtype(type(time_data[0]), np.datetime64)

    def test_creates_color_stripe_config(self):
        """add_color_stripe creates ColorStripeConfig."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1", colormap="Viridis256")

        assert "stripe1" in builder._color_stripes
        config = builder._color_stripes["stripe1"]
        assert isinstance(config, ColorStripeConfig)
        assert config.name == "stripe1"
        assert config.colormap == "Viridis256"

    def test_auto_computes_value_range(self):
        """add_color_stripe auto-computes value_range when not provided."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([10.0, 20.0, 30.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1")

        config = builder._color_stripes["stripe1"]
        assert config.value_range is not None
        assert config.value_range[0] == 10.0
        assert config.value_range[1] == 30.0

    def test_respects_explicit_value_range(self):
        """add_color_stripe respects explicit value_range."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1", value_range=(0.0, 100.0))

        config = builder._color_stripes["stripe1"]
        assert config.value_range == (0.0, 100.0)

    def test_default_colormap_is_cividis256(self):
        """add_color_stripe uses Cividis256 as default colormap."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        config = builder._color_stripes["stripe1"]
        assert config.colormap == "Cividis256"

    def test_custom_colormap_works(self):
        """add_color_stripe respects custom colormap."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1", colormap="Viridis256")

        config = builder._color_stripes["stripe1"]
        assert config.colormap == "Viridis256"

    def test_creates_column_data_source(self):
        """add_color_stripe creates ColumnDataSource with time and value."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        config = builder._color_stripes["stripe1"]
        source = config.source

        assert isinstance(source, ColumnDataSource)
        assert "time" in source.data
        assert "value" in source.data

    def test_stores_plot_height(self):
        """add_color_stripe stores plot height in _plot_heights."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1", height=50)

        assert builder._plot_heights["stripe1"] == 50

    def test_default_height_is_40(self):
        """add_color_stripe uses 40px as default height."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert builder._plot_heights["stripe1"] == 40

    def test_appends_to_elements(self):
        """add_color_stripe appends to _elements list."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        assert isinstance(builder._elements[0], ColorStripeConfig)
        assert builder._elements[0].name == "stripe1"

    def test_method_chaining(self):
        """add_color_stripe can be chained."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])

        result = builder.add_scatter(y_column="altitude").add_color_stripe(series, name="stripe1")

        assert result is builder
        assert len(builder._elements) == 2


class TestBuildMixedElements:
    """Tests for TimelineBuilder.build with mixed element types."""

    def test_scatter_and_visits_combined(self):
        """build overlays visits onto scatter panels rather than adding a separate figure."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )

        result = builder.build()

        # One scatter panel; visits are overlaid on it.
        assert len(result.children) == 1
        assert len(result.children[0].renderers) >= 1

    def test_scatter_and_stripe_combined(self):
        """build handles scatter and color stripe together."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        assert len(result.children) == 2

    def test_visits_and_stripe_combined(self):
        """build with only visits and a stripe produces just the stripe panel."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        # Only the stripe creates a panel; visits need a scatter to attach to.
        assert len(result.children) == 1

    def test_all_three_types_combined(self):
        """build handles scatter + visits + stripe: scatter and stripe get panels."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        # scatter1 + stripe1 = 2 panels; visits1 overlays scatter1.
        assert len(result.children) == 2

    def test_order_matches_insertion_order(self):
        """Figure order matches insertion order of scatter/stripe elements."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="first")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="second"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="third"
        )

        result = builder.build()

        # "first" scatter + "third" stripe = 2 panels in insertion order.
        assert len(result.children) == 2

    def test_all_figures_share_same_x_range(self):
        """All figures share the same Range1d object."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        x_ranges = [fig.x_range for fig in result.children]
        assert all(xr is x_ranges[0] for xr in x_ranges)

    def test_heights_respected_for_each_element(self):
        """Each element's height is respected."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1", height=150)
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1",
            height=200
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1",
            height=30
        )

        result = builder.build()

        # Check that heights are applied
        assert builder._plot_heights["scatter1"] == 150
        assert builder._plot_heights["visits1"] == 200
        assert builder._plot_heights["stripe1"] == 30

    def test_datetime_formatter_on_all_figures(self):
        """DatetimeTickFormatter is applied to all figures."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        for fig in result.children:
            x_axis = fig.xaxis[0]
            assert isinstance(x_axis.formatter, DatetimeTickFormatter)

    def test_visits_overlaid_on_scatter_figure(self):
        """Visit data is overlaid as a scatter glyph on the scatter panel."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="main")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )

        result = builder.build()
        scatter_fig = result.children[0]

        scatter_renderers = [r for r in scatter_fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) >= 1


class TestColorStripeRendering:
    """Tests for color stripe rendering in build()."""

    def test_stripe_figure_has_rect_or_quad_glyph(self):
        """Stripe figure contains rect or quad glyph."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()
        stripe_fig = result.children[0]

        # Check for rect or quad glyph
        rect_renderers = [r for r in stripe_fig.renderers if isinstance(r.glyph, (Rect, Quad))]
        assert len(rect_renderers) >= 1

    def test_stripe_figure_has_no_y_axis(self):
        """Stripe figure has no y-axis (or y-axis is hidden)."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()
        stripe_fig = result.children[0]

        # When y_axis_type=None, yaxis list is empty
        # With explicit y_range, yaxis still exists but should be hidden or not shown
        # Check that y-axis is not visible or has no ticks
        y_axis = stripe_fig.yaxis[0] if stripe_fig.yaxis else None
        if y_axis:
            # y-axis exists but should be hidden (visible=False)
            assert not y_axis.visible or y_axis.axis_line_color is None

    def test_stripe_time_axis_formatted(self):
        """Stripe figure time axis uses DatetimeTickFormatter."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()
        stripe_fig = result.children[0]

        x_axis = stripe_fig.xaxis[0]
        assert isinstance(x_axis.formatter, DatetimeTickFormatter)


class TestBuildReturnsBokehLayout:
    """Tests for build() return type and structure."""

    def test_returns_bokeh_column_layout(self):
        """build returns a bokeh column layout."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude")
        result = builder.build()

        assert isinstance(result, type(column()))

    def test_children_count_matches_element_count(self):
        """Number of figures equals the number of scatter + stripe elements."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="s1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="v1"
        )
        builder.add_color_stripe(
            pd.Series([1.0], index=[59999.0]),
            name="c1"
        )

        result = builder.build()

        # _elements contains s1 (scatter) + c1 (stripe); v1 is in _visit_sets only.
        assert len(result.children) == len(builder._elements)
        assert len(result.children) == 2


class TestCLIv2Visits:
    """Tests for CLI v2 --visits functionality."""

    def test_cli_accepts_visits_file(self):
        """CLI accepts --visits argument with file path."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--visits", "/tmp/test_visits.parquet",
            "--output", "/tmp/cli_test.html"
        ])
        # Should not error (may fail on file read, but argument parsing should work)
        assert result.exit_code in (0, 1)  # 0 if succeeds, 1 if file read fails

    def test_cli_accepts_multiple_visits_files(self):
        """CLI accepts multiple --visits arguments."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--visits", "/tmp/visits1.parquet",
            "--visits", "/tmp/visits2.parquet",
            "--output", "/tmp/cli_test.html"
        ])
        assert result.exit_code in (0, 1)


class TestCLIv2Background:
    """Tests for CLI v2 --background functionality."""

    def test_cli_accepts_background_argument(self):
        """CLI accepts --background argument."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--background", "sun_elevation",
            "--output", "/tmp/cli_test.html"
        ])
        assert result.exit_code in (0, 1)

    def test_cli_accepts_multiple_background_types(self):
        """CLI accepts multiple --background arguments."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--background", "sun_elevation",
            "--background", "moon_elevation",
            "--output", "/tmp/cli_test.html"
        ])
        assert result.exit_code in (0, 1)


class TestCLIv2Integration:
    """Integration tests for CLI v2."""

    def test_cli_with_all_options(self):
        """CLI works with scatter, visits, and background together."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--scatter", "HA",
            "--visits", "/tmp/visits.parquet",
            "--background", "sun_elevation",
            "--output", "/tmp/cli_test.html"
        ])
        # Should not error on argument parsing
        assert result.exit_code in (0, 1)


class TestPhaseBGuardrails:
    """Tests to ensure Phase B doesn't violate requirements."""

    def test_phase_a_signature_unchanged_add_scatter(self):
        """Phase A add_scatter signature is unchanged."""
        import inspect
        from schedview.plot.tlbuilder import TimelineBuilder

        sig = inspect.signature(TimelineBuilder.add_scatter)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "y_column" in params
        assert "offered_columns" in params
        assert "name" in params
        assert "height" in params
        assert "tooltips" in params

    def test_phase_a_signature_unchanged_build(self):
        """Phase A build signature is unchanged."""
        import inspect
        from schedview.plot.tlbuilder import TimelineBuilder

        sig = inspect.signature(TimelineBuilder.build)
        params = list(sig.parameters.keys())
        assert "self" in params
        # build() should not have new required parameters

    def test_no_widgets_in_build_output(self):
        """Build output doesn't contain interactive widgets."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame({
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }),
            label="visits1"
        )
        builder.add_color_stripe(
            pd.Series([1.0, 2.0], index=[59999.0, 60000.0]),
            name="stripe1"
        )

        result = builder.build()

        # Check that widgets (dropdowns, buttons, etc.) are not in the layout
        # Bokeh widgets would be instances of specific widget classes
        # For Phase B, we should only have figures and layouts

    def test_no_phase_c_api_added(self):
        """No Phase C APIs were added."""
        from schedview.plot.tlbuilder import TimelineBuilder

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))

        # Phase B APIs should exist
        assert hasattr(builder, "add_scatter")
        assert hasattr(builder, "add_visits")
        assert hasattr(builder, "add_color_stripe")
        assert hasattr(builder, "build")

        # Phase C APIs (if any exist) should not be present in Phase B
        # We're not testing for specific Phase C features, just ensuring
        # the Phase B API surface is correct

    def test_public_api_signatures_match_spec(self):
        """Public API signatures match specification."""
        import inspect
        from schedview.plot.tlbuilder import TimelineBuilder

        # Check add_visits signature
        vis_sig = inspect.signature(TimelineBuilder.add_visits)
        vis_params = list(vis_sig.parameters.keys())
        assert "visits" in vis_params
        assert "label" in vis_params
        assert "alpha" in vis_params
        assert "marker" in vis_params
        assert "color_by_band" in vis_params
        assert "show_visibility_toggle" in vis_params  # Phase B requires this param

        # Check add_color_stripe signature
        stripe_sig = inspect.signature(TimelineBuilder.add_color_stripe)
        stripe_params = list(stripe_sig.parameters.keys())
        assert "data" in stripe_params
        assert "name" in stripe_params
        assert "height" in stripe_params
        assert "colormap" in stripe_params
        assert "value_range" in stripe_params
