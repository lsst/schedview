"""Test suite for tlbuilder.

This file contains tests for the TimelineBuilder class and related components
in the schedview.plot.tlbuilder module.
"""

from __future__ import annotations

from unittest.mock import patch

import click
import numpy as np
import pandas as pd
import pytest
from astropy.time import Time
from bokeh.layouts import column
from bokeh.models import (
    ColumnDataSource,
    CustomJS,
    DatetimeTickFormatter,
    HoverTool,
    MultiChoice,
    Quad,
    Range1d,
    Rect,
    Scatter,
    Select,
)
from bokeh.plotting import figure
from click.testing import CliRunner

from schedview.dayobs import DayObs
from schedview.plot.tlbuilder import (
    ColorStripeConfig,
    ScatterPlotConfig,
    TimelineBuilder,
    VisitDataSet,
)

# ============================================================================
# Dataclass Tests
# ============================================================================


class TestScatterPlotConfig:
    """Tests for ScatterPlotConfig dataclass."""

    def test_stores_name(self):
        """ScatterPlotConfig stores name correctly."""
        config = ScatterPlotConfig(
            name="test_plot",
            y_column="altitude",
            offered_columns=(),
            figure_kwargs={},
        )
        assert config.name == "test_plot"

    def test_stores_y_column(self):
        """ScatterPlotConfig stores y_column correctly."""
        config = ScatterPlotConfig(
            name="test_plot",
            y_column="altitude",
            offered_columns=(),
            figure_kwargs={},
        )
        assert config.y_column == "altitude"

    def test_stores_offered_columns(self):
        """ScatterPlotConfig stores offered_columns correctly."""
        offered = ("altitude", "HA", "fieldRA")
        config = ScatterPlotConfig(
            name="test_plot",
            y_column="altitude",
            offered_columns=offered,
            figure_kwargs={},
        )
        assert config.offered_columns == offered

    def test_stores_figure_kwargs(self):
        """ScatterPlotConfig stores figure_kwargs correctly."""
        kwargs = {"width": 800}
        config = ScatterPlotConfig(
            name="test_plot",
            y_column="altitude",
            offered_columns=(),
            figure_kwargs=kwargs,
        )
        assert config.figure_kwargs == kwargs


class TestColorStripeConfig:
    """Tests for ColorStripeConfig dataclass."""

    def test_class_exists(self):
        """ColorStripeConfig class exists."""
        assert ColorStripeConfig is not None

    def test_can_instantiate(self):
        """ColorStripeConfig can be instantiated with required args."""
        source = ColumnDataSource(data={"time": [], "value": []})
        config = ColorStripeConfig(
            name="test_stripe", source=source, colormap="Cividis256", value_range=(0.0, 1.0)
        )
        assert config is not None
        assert config.name == "test_stripe"
        assert config.colormap == "Cividis256"


class TestVisitDataSet:
    """Tests for VisitDataSet dataclass."""

    def test_class_exists(self):
        """VisitDataSet class exists."""
        assert VisitDataSet is not None

    def test_can_instantiate(self):
        """VisitDataSet can be instantiated."""
        dataset = VisitDataSet()
        assert dataset is not None

    def test_default_values(self):
        """VisitDataSet has expected default values."""
        dataset = VisitDataSet()
        assert dataset.alpha == 1.0
        assert dataset.marker is None
        assert dataset.show_visibility_toggle is True

    def test_custom_values(self):
        """VisitDataSet stores custom values correctly."""
        source = ColumnDataSource(data={"time": [], "altitude": []})
        dataset = VisitDataSet(
            source=source,
            label="custom_visits",
            alpha=0.5,
            marker="triangle",
            show_visibility_toggle=False,
        )
        assert dataset.source is source
        assert dataset.label == "custom_visits"
        assert dataset.alpha == 0.5
        assert dataset.marker == "triangle"
        assert dataset.show_visibility_toggle is False


# ============================================================================
# TimelineBuilder Initialization Tests
# ============================================================================


class TestTimelineBuilderInitialization:
    """Tests for TimelineBuilder initialization."""

    def test_stores_dayobs(self):
        """TimelineBuilder stores dayobs correctly."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._dayobs is dayobs

    def test_initializes_empty_elements(self):
        """TimelineBuilder initializes _elements as empty list."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._elements == []

    def test_initializes_empty_visit_sets(self):
        """TimelineBuilder initializes _visit_sets as empty dict."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._visit_sets == {}

    def test_initializes_shared_x_range(self):
        """TimelineBuilder initializes _shared_x_range from dayobs."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert isinstance(builder._shared_x_range, Range1d)

    def test_initializes_figure_kwargs(self):
        """TimelineBuilder initializes _figure_kwargs with defaults."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._figure_kwargs == {"width": 1000}

    def test_initializes_plot_heights(self):
        """TimelineBuilder initializes _plot_heights as empty dict."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._plot_heights == {}


# ============================================================================
# TimelineBuilder.add_scatter Tests
# ============================================================================


class TestAddScatter:
    """Tests for TimelineBuilder.add_scatter method."""

    def test_returns_self_for_chaining(self):
        """add_scatter returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        result = builder.add_scatter(y_column="altitude")
        assert result is builder

    def test_appends_scatter_config(self):
        """add_scatter appends ScatterPlotConfig to _elements."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="my_scatter")
        assert len(builder._elements) == 1
        assert isinstance(builder._elements[0], ScatterPlotConfig)
        assert builder._elements[0].name == "my_scatter"
        assert builder._elements[0].y_column == "altitude"

    def test_appends_multiple_scatters(self):
        """add_scatter appends multiple configs correctly."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude").add_scatter(y_column="HA", name="ha_plot")
        assert len(builder._elements) == 2
        assert builder._elements[0].name == "scatter"
        assert builder._elements[1].name == "ha_plot"

    def test_stores_height_if_provided(self):
        """add_scatter stores height in _plot_heights if provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", height=250)
        assert builder._plot_heights["scatter"] == 250

    def test_stores_custom_name_height(self):
        """add_scatter stores height with custom name."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="my_plot", height=300)
        assert builder._plot_heights["my_plot"] == 300

    def test_offered_columns_stored(self):
        """add_scatter stores offered_columns in config."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        offered = ("altitude", "HA", "fieldRA")
        builder.add_scatter(y_column="altitude", offered_columns=offered)
        assert builder._elements[0].offered_columns == offered

    def test_offered_columns_merge_multiple_sources(self):
        """offered_columns from multiple --y-columns are merged."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # Simulate merging multiple --y-columns values like the CLI does
        offered1 = ("altitude", "HA")
        offered2 = ("fieldRA", "fiveSigmaDepth")
        # Build merged offered_columns (like CLI does)
        all_columns = []
        all_columns.extend(c.strip() for c in ",".join(offered1).split(",") if c.strip())
        all_columns.extend(c.strip() for c in ",".join(offered2).split(",") if c.strip())
        merged = tuple(all_columns)
        builder.add_scatter(y_column="altitude", offered_columns=merged)
        assert builder._elements[0].offered_columns == merged
        assert len(builder._elements[0].offered_columns) == 4

    def test_figure_kwargs_stored(self):
        """add_scatter stores figure_kwargs in config."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        kwargs = {"width": 800}
        builder.add_scatter(y_column="altitude", **kwargs)
        assert builder._elements[0].figure_kwargs == {"width": 800}

    def test_shared_x_range_exists_before_scatter(self):
        """Shared x-range is initialized in the constructor."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._shared_x_range is not None
        builder.add_scatter(y_column="altitude")
        assert builder._shared_x_range is not None

    def test_shared_x_range_is_range1d(self):
        """Shared x-range is a Range1d instance."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        assert isinstance(builder._shared_x_range, Range1d)

    def test_shared_x_range_bounds_from_dayobs(self):
        """Shared x-range uses DayObs sunset/sunrise times as datetime64."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        x_range = builder._shared_x_range

        expected_start = Time(float(dayobs.sunset.mjd), format="mjd").datetime64
        expected_end = Time(float(dayobs.sunrise.mjd), format="mjd").datetime64

        assert x_range.start == expected_start
        assert x_range.end == expected_end

    def test_shared_x_range_same_on_multiple_calls(self):
        """Shared x-range is the same object on multiple add_scatter calls."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))

        builder.add_scatter(y_column="altitude")
        first_range = builder._shared_x_range

        builder.add_scatter(y_column="HA")
        second_range = builder._shared_x_range

        assert first_range is second_range


# ============================================================================
# TimelineBuilder.add_visits Tests
# ============================================================================


class TestAddVisits:
    """Tests for TimelineBuilder.add_visits method."""

    def test_returns_self_for_chaining(self):
        """add_visits returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        result = builder.add_visits(pd.DataFrame(), label="test_visits")
        assert result is builder

    def test_accepts_visits_dataframe(self):
        """add_visits accepts a pandas DataFrame."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0, 60001.0],
                "altitude": [30.0, 45.0, 60.0],
            }
        )
        builder.add_visits(visits_df)
        assert "visits" in builder._visit_sets

    def test_converts_mjd_to_datetime64(self):
        """add_visits converts MJD timestamps to datetime64."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0, 60001.0],
                "altitude": [30.0, 45.0, 60.0],
            }
        )
        builder.add_visits(visits_df)

        dataset = builder._visit_sets["visits"]
        source = dataset.source
        time_data = source.data.get("time", [])

        if len(time_data) > 0:
            assert isinstance(time_data[0], np.datetime64)

    def test_creates_column_data_source(self):
        """add_visits creates a ColumnDataSource with correct fields."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "band": ["g", "r"],
            }
        )
        builder.add_visits(visits_df)

        dataset = builder._visit_sets["visits"]
        assert isinstance(dataset.source, ColumnDataSource)
        source = dataset.source
        assert "time" in source.data
        assert "altitude" in source.data
        assert "band" in source.data

    def test_stores_visit_dataset(self):
        """add_visits stores VisitDataSet in self._visit_sets."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="my_visits")

        assert "my_visits" in builder._visit_sets
        dataset = builder._visit_sets["my_visits"]
        assert isinstance(dataset, VisitDataSet)

    def test_stores_visit_dataset_attributes(self):
        """VisitDataSet stores label, alpha, marker."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="test_visits", alpha=0.7, marker="triangle")

        dataset = builder._visit_sets["test_visits"]
        assert dataset.label == "test_visits"
        assert dataset.alpha == 0.7
        assert dataset.marker == "triangle"

    def test_applies_band_coloring_by_default_when_band_exists(self):
        """By default, add_visits assigns colors based on band using the band column."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0, 60001.0],
                "altitude": [30.0, 45.0, 60.0],
                "band": ["u", "g", "r"],
            }
        )
        builder.add_visits(visits_df, label="band_visits")

        dataset = builder._visit_sets["band_visits"]
        source = dataset.source
        # Band values should be in source data for color mapping
        assert "band" in source.data

    def test_visits_data_stores_band_column(self):
        """add_visits stores band column in source for color mapping."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="default_band")

        dataset = builder._visit_sets["default_band"]
        source = dataset.source
        # Band column should be available in source
        assert "band" in source.data
        assert source.data["band"][0] == "g"

    def test_custom_marker_works(self):
        """add_visits respects custom marker parameter."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="triangle_visits", marker="triangle")

        dataset = builder._visit_sets["triangle_visits"]
        assert dataset.marker == "triangle"

    def test_custom_alpha_works(self):
        """add_visits respects custom alpha parameter."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="alpha_visits", alpha=0.3)

        dataset = builder._visit_sets["alpha_visits"]
        assert dataset.alpha == 0.3

    def test_custom_time_column(self):
        """add_visits can use custom time column."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "custom_time_mjd": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
            }
        )
        builder.add_visits(visits_df, label="custom_time", time_column="custom_time_mjd")

        dataset = builder._visit_sets["custom_time"]
        assert "time" in dataset.source.data

    def test_method_chaining(self):
        """add_visits can be chained with other methods."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )

        result = (
            builder.add_scatter(y_column="altitude", name="scatter1")
            .add_visits(visits_df, label="visits1")
            .add_scatter(y_column="HA", name="scatter2")
        )

        assert result is builder
        assert len(builder._elements) == 2
        assert "visits1" in builder._visit_sets


# ============================================================================
# TimelineBuilder.map_colors Tests
# ============================================================================


class TestMapColors:
    """Tests for TimelineBuilder.map_colors method."""

    def test_returns_self_for_chaining(self):
        """map_colors returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        result = builder.map_colors("band")
        assert result is builder

    def test_sets_color_column_to_band(self):
        """map_colors sets color_column to specified value."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.map_colors("band")
        assert builder._color_column == "band"

    def test_sets_color_column_to_custom_column(self):
        """map_colors can set color_column to any column name."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.map_colors("airmass")
        assert builder._color_column == "airmass"

    def test_default_color_column_is_band(self):
        """Default color_column is 'band'."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._color_column == "band"

    def test_method_chaining(self):
        """map_colors can be chained with other builder methods."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        result = builder.map_colors("band").add_scatter(y_column="altitude").add_visits(visits_df)
        assert result is builder


# ============================================================================
# Color Mapping Tests
# ============================================================================


class TestColorMapping:
    """Tests for color mapping in scatter plots."""

    def test_default_band_palette_used(self):
        """Default band column uses PLOT_BAND_COLORS palette."""
        from schedview.plot.colors import PLOT_BAND_COLORS

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "band": ["g", "r"],
            }
        )
        builder.add_visits(visits_df, label="visits")
        builder.add_scatter(y_column="altitude", name="scatter1")
        result = builder.build()

        # The scatter should have renderers with color encoding
        fig = result.children[0]  # First scatter plot
        scatter_renderers = [r for r in fig.renderers if hasattr(r.glyph, "fill_color")]
        assert len(scatter_renderers) >= 1

    def test_non_band_column_uses_colorblind_palette(self):
        """Non-band color column uses Colorblind palette."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "visitType": ["deep", "wide"],
            }
        )
        builder.map_colors("visitType")
        builder.add_visits(visits_df, label="visits")
        builder.add_scatter(y_column="altitude", name="scatter1")
        result = builder.build()

        # Should have renderers
        fig = result.children[0]
        scatter_renderers = [r for r in fig.renderers if hasattr(r.glyph, "fill_color")]
        assert len(scatter_renderers) >= 1

    def test_many_distinct_values_get_other_bin(self):
        """Many distinct values in color column are collapsed to 'other'."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # Create visit data with more distinct values than Colorblind palette (8)
        num_visits = 20
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0 + i / 100 for i in range(num_visits)],
                "altitude": [30.0 + i for i in range(num_visits)],
                "visitId": [f"v{i}" for i in range(num_visits)],
            }
        )
        builder.map_colors("visitId")
        builder.add_visits(visits_df, label="visits")
        builder.add_scatter(y_column="altitude", name="scatter1")
        result = builder.build()

        # Should build successfully without error
        assert result is not None


# ============================================================================
# Helper function Tests
# ============================================================================


class TestFindTimeColumn:
    """Tests for _find_time_column helper function."""

    def test_returns_explicit_time_column(self):
        """_find_time_column returns explicit time_column when provided."""
        from schedview.plot.tlbuilder import _find_time_column

        df = pd.DataFrame({"timestamp": [1.0, 2.0], "value": [10.0, 20.0]})
        result = _find_time_column(df, time_column="timestamp")
        assert result == "timestamp"

    def test_heuristic_finds_mjd_column(self):
        """_find_time_column heuristic finds column with 'mjd' in name."""
        from schedview.plot.tlbuilder import _find_time_column

        df = pd.DataFrame(
            {
                "observationStartMJD": [1.0, 2.0],
                "value": [10.0, 20.0],
            }
        )
        result = _find_time_column(df)
        assert result == "observationStartMJD"

    def test_heuristic_finds_lowercase_mjd(self):
        """_find_time_column heuristic is case-insensitive for 'mjd'."""
        from schedview.plot.tlbuilder import _find_time_column

        df = pd.DataFrame(
            {
                "time_mjd": [1.0, 2.0],
                "value": [10.0, 20.0],
            }
        )
        result = _find_time_column(df)
        assert result == "time_mjd"

    def test_heuristic_finds_first_column_when_no_mjd(self):
        """_find_time_column uses first column when no 'mjd' found."""
        from schedview.plot.tlbuilder import _find_time_column

        df = pd.DataFrame(
            {
                "timestamp": [1.0, 2.0],
                "value": [10.0, 20.0],
            }
        )
        result = _find_time_column(df)
        assert result == "timestamp"

    def test_heuristic_prefers_mjd_over_first_column(self):
        """_find_time_column prefers 'mjd' column over first column."""
        from schedview.plot.tlbuilder import _find_time_column

        df = pd.DataFrame(
            {
                "first_col": [0.0, 1.0],
                "observationStartMJD": [1.0, 2.0],
                "value": [10.0, 20.0],
            }
        )
        result = _find_time_column(df)
        assert result == "observationStartMJD"


# ============================================================================
# TimelineBuilder.add_color_stripe Tests
# ============================================================================


class TestAddColorStripe:
    """Tests for TimelineBuilder.add_color_stripe method."""

    def test_returns_self_for_chaining(self):
        """add_color_stripe returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        result = builder.add_color_stripe(series, name="test_stripe")
        assert result is builder

    def test_accepts_series_indexed_by_mjd(self):
        """add_color_stripe accepts a Series indexed by MJD."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="test_stripe")
        assert len(builder._elements) == 1

    def test_accepts_dataframe_with_mjd_column(self):
        """add_color_stripe accepts a DataFrame with MJD column."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        df = pd.DataFrame(
            {
                "time_mjd": [59999.0, 60000.0, 60001.0],
                "value": [1.0, 2.0, 3.0],
            }
        )
        builder.add_color_stripe(df, name="test_stripe", value_column="value")
        assert len(builder._elements) == 1

    def test_converts_mjd_to_datetime64(self):
        """add_color_stripe converts MJD to datetime64."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        stripe_config = builder._elements[0]
        assert isinstance(stripe_config, ColorStripeConfig)
        assert stripe_config.name == "stripe1"
        source = stripe_config.source
        time_data = source.data.get("time", [])

        if len(time_data) > 0:
            assert isinstance(time_data[0], np.datetime64)

    def test_creates_color_stripe_config(self):
        """add_color_stripe creates ColorStripeConfig."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1", colormap="Viridis256")

        assert len(builder._elements) == 1
        config = builder._elements[0]
        assert isinstance(config, ColorStripeConfig)
        assert config.name == "stripe1"
        assert config.colormap == "Viridis256"

    def test_auto_computes_value_range(self):
        """add_color_stripe auto-computes value_range when not provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([10.0, 20.0, 30.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        config = builder._elements[0]
        assert config.value_range is not None
        assert config.value_range[0] == 10.0
        assert config.value_range[1] == 30.0

    def test_respects_explicit_value_range(self):
        """add_color_stripe respects explicit value_range."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0, 3.0], index=[59999.0, 60000.0, 60001.0])
        builder.add_color_stripe(series, name="stripe1", value_range=(0.0, 100.0))

        assert len(builder._elements) == 1
        config = builder._elements[0]
        assert config.value_range == (0.0, 100.0)

    def test_default_colormap_is_cividis256(self):
        """add_color_stripe uses Cividis256 as default colormap."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        config = builder._elements[0]
        assert config.colormap == "Cividis256"

    def test_custom_colormap_works(self):
        """add_color_stripe respects custom colormap."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1", colormap="Viridis256")

        assert len(builder._elements) == 1
        config = builder._elements[0]
        assert config.colormap == "Viridis256"

    def test_creates_column_data_source(self):
        """add_color_stripe creates ColumnDataSource with time and value."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        config = builder._elements[0]
        source = config.source

        assert isinstance(source, ColumnDataSource)
        assert "time" in source.data
        assert "value" in source.data

    def test_stores_plot_height(self):
        """add_color_stripe stores plot height in _plot_heights."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1", height=50)

        assert builder._plot_heights["stripe1"] == 50

    def test_default_height_is_40(self):
        """add_color_stripe uses 40px as default height."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert builder._plot_heights["stripe1"] == 40

    def test_appends_to_elements(self):
        """add_color_stripe appends to _elements list."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        builder.add_color_stripe(series, name="stripe1")

        assert len(builder._elements) == 1
        assert isinstance(builder._elements[0], ColorStripeConfig)
        assert builder._elements[0].name == "stripe1"

    def test_method_chaining(self):
        """add_color_stripe can be chained."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])

        result = builder.add_scatter(y_column="altitude").add_color_stripe(series, name="stripe1")

        assert result is builder
        assert len(builder._elements) == 2

    def test_explicit_time_column_with_dataframe(self):
        """add_color_stripe uses explicit time_column when provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # DataFrame with a non-standard time column name
        df = pd.DataFrame(
            {
                "timestamp": [59999.0, 60000.0, 60001.0],  # Not 'time_mjd' or含有 'mjd'
                "value": [1.0, 2.0, 3.0],
            }
        )
        builder.add_color_stripe(df, name="stripe1", time_column="timestamp", value_column="value")
        assert len(builder._elements) == 1

        # Verify the time data was correctly extracted
        config = builder._elements[0]
        source = config.source
        time_data = source.data.get("time", [])
        assert len(time_data) == 3
        assert isinstance(time_data[0], np.datetime64)

    def test_explicit_time_column_overrides_heuristic(self):
        """add_color_stripe uses explicit time_column over heuristic."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # DataFrame with multiple numeric columns
        df = pd.DataFrame(
            {
                "time_mjd": [59998.0, 59999.0, 60000.0],  # Heuristic would pick this
                "timestamp": [59999.0, 60000.0, 60001.0],  # But we want this one
                "value": [1.0, 2.0, 3.0],
            }
        )
        # Explicit time_column should override the heuristic
        builder.add_color_stripe(df, name="stripe1", time_column="timestamp", value_column="value")

        config = builder._elements[0]
        source = config.source
        time_data = source.data.get("time", [])

        # With explicit time_column="timestamp", times should match input
        # Convert back to MJD for comparison
        mjds = []
        for t in time_data:
            mjd = Time(t, format="datetime64").mjd
            mjds.append(round(mjd))
        assert mjds == [59999, 60000, 60001]

    def test_time_column_with_series_ignored(self):
        """add_color_stripe time_column is ignored for Series (uses index)."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # time_column should be ignored for Series
        series = pd.Series([1.0, 2.0], index=[59999.0, 60000.0])
        # time_column argument should not cause issues
        builder.add_color_stripe(series, name="stripe1", time_column="some_column")

        config = builder._elements[0]
        source = config.source
        time_data = source.data.get("time", [])

        # Times should come from Series index, not time_column
        mjds = []
        for t in time_data:
            mjd = Time(t, format="datetime64").mjd
            mjds.append(round(mjd))
        assert mjds == [59999, 60000]

    def test_handles_mixed_finite_and_nan_values(self):
        """add_color_stripe uses nanmin/nanmax for mixed finite+NaN values."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # Mixed finite and NaN
        series = pd.Series(
            [1.0, np.nan, 5.0, np.nan, 10.0],
            index=[59999.0, 60000.0, 60001.0, 60002.0, 60003.0],
        )
        builder.add_color_stripe(series, name="mixed_stripe")

        config = builder._elements[0]
        # Should compute range using only finite values
        assert config.value_range == (1.0, 10.0)

    def test_handles_all_nan_values_raises_error(self):
        """add_color_stripe raises ValueError for all-NaN values."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # All NaN values
        series = pd.Series([np.nan, np.nan, np.nan], index=[59999.0, 60000.0, 60001.0])

        with pytest.raises(ValueError, match="no finite values|all-NaN|empty"):
            builder.add_color_stripe(series, name="all_nan_stripe")

    def test_handles_empty_series_raises_error(self):
        """add_color_stripe raises ValueError for empty series."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # Empty Series
        series = pd.Series([], dtype=float, index=[])

        with pytest.raises(ValueError, match="no finite values|all-NaN|empty"):
            builder.add_color_stripe(series, name="empty_stripe")

    def test_handles_dataframe_with_nan_values(self):
        """add_color_stripe handles DataFrame with NaN values correctly."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        df = pd.DataFrame(
            {
                "time_mjd": [59999.0, 60000.0, 60001.0],
                "value": [np.nan, 5.0, 15.0],
            }
        )
        builder.add_color_stripe(df, name="nan_stripe", value_column="value")

        config = builder._elements[0]
        # Should compute range using only finite values
        assert config.value_range == (5.0, 15.0)


# ============================================================================
# TimelineBuilder.add_visit_visibility_selector Tests
# ============================================================================


class TestAddVisitVisibilitySelector:
    """Tests for TimelineBuilder.add_visit_visibility_selector method."""

    def test_multichoice_widget_added(self):
        """add_visit_visibility_selector adds a MultiChoice widget."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        result = builder.add_visit_visibility_selector()
        builder.build()  # Build to create the selector

        assert result is builder
        assert hasattr(builder, "_visibility_selector")
        assert isinstance(builder._visibility_selector, MultiChoice)

    def test_widget_options_match_visit_labels(self):
        """Widget options match visit labels when visibility toggle is True."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visible_visit", show_visibility_toggle=True)
        builder.add_visits(visits_df, label="hidden_visit", show_visibility_toggle=False)
        builder.add_visits(visits_df, label="another_visible", show_visibility_toggle=True)

        builder.add_visit_visibility_selector()
        builder.build()  # Build to create the selector

        widget = builder._visibility_selector
        assert "visible_visit" in widget.options
        assert "another_visible" in widget.options
        assert "hidden_visit" not in widget.options

    def test_widget_positioned_above_plots(self):
        """Visibility selector appears once above all plots in final layout."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_scatter(y_column="HA", name="scatter2")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        builder.add_visits(visits_df, label="visit2", show_visibility_toggle=True)
        builder.add_visit_visibility_selector()
        result = builder.build()

        assert len(result.children) >= 3  # selector + 2 scatter plots
        first_child = result.children[0]
        assert isinstance(first_child, MultiChoice)

    def test_customjs_callback_toggles_visibility(self):
        """CustomJS callback toggles .visible for visit set renderers."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        builder.add_visits(visits_df, label="visit2", show_visibility_toggle=True)
        builder.add_visit_visibility_selector()
        result = builder.build()

        widget = result.children[0]
        assert isinstance(widget, MultiChoice)

        callbacks = widget.js_property_callbacks.get("change:value", [])
        assert len(callbacks) > 0
        has_customjs = any(isinstance(cb, CustomJS) for cb in callbacks)
        assert has_customjs

    def test_callback_affects_only_visit_renderers(self):
        """Visibility toggle affects only visit set renderers."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        builder.add_visit_visibility_selector()
        result = builder.build()

        fig = result.children[1]  # Skip selector, get first scatter
        scatter_renderers = [r for r in fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) >= 1


# ============================================================================
# TimelineBuilder.add_visit_visibility_selector robustness Tests
# ============================================================================


class TestVisitVisibilitySelectorCallOrder:
    """Tests for robustness of add_visit_visibility_selector to call order."""

    def test_selector_called_before_visits(self):
        """Selector works correctly when called before visits are added."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )

        # Add selector BEFORE visits - should still work
        builder.add_visit_visibility_selector()
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)

        result = builder.build()

        # Selector should exist and have correct options
        assert isinstance(result.children[0], MultiChoice)
        widget = result.children[0]
        assert "visit1" in widget.options

    def test_selector_called_after_visits(self):
        """Selector works correctly when called after visits are added."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)

        # Add selector AFTER visits
        builder.add_visit_visibility_selector()

        result = builder.build()

        assert isinstance(result.children[0], MultiChoice)
        widget = result.children[0]
        assert "visit1" in widget.options

    def test_multiple_visits_added_after_selector(self):
        """Multiple visits added after selector are all included."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )

        # Add selector first
        builder.add_visit_visibility_selector()

        # Add multiple visits after
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        builder.add_visits(visits_df, label="visit2", show_visibility_toggle=True)
        builder.add_visits(visits_df, label="visit3", show_visibility_toggle=False)

        result = builder.build()

        widget = result.children[0]
        assert "visit1" in widget.options
        assert "visit2" in widget.options
        assert "visit3" not in widget.options

    def test_no_selector_when_no_visits_with_toggle(self):
        """Selector not created when no visits have toggle enabled."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=False)

        builder.add_visit_visibility_selector()
        result = builder.build()

        # No selector should be created since no visits have toggle enabled
        assert not isinstance(result.children[0], MultiChoice)
        # The first child should be the scatter figure
        assert isinstance(result.children[0], figure)


# ============================================================================
# TimelineBuilder.add_scatter_y_selector Tests
# ============================================================================


class TestScatterYAxisSelector:
    """Tests for scatter y-axis selector widgets."""

    def test_select_widget_created_for_multiple_offered_columns(self):
        """Y-axis selector created for multiple offered_columns."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "fieldRA"], name="scatter1"
        )
        result = builder.build()

        assert len(result.children) >= 2  # selector + figure
        first_child = result.children[0]
        assert isinstance(first_child, Select)

    def test_no_widget_for_empty_offered_columns(self):
        """No y-axis selector when offered_columns is empty."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=[], name="scatter1")
        result = builder.build()

        first_child = result.children[0]
        assert not isinstance(first_child, Select)

    def test_no_widget_for_single_offered_column(self):
        """No y-axis selector when offered_columns has only one item."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude"], name="scatter1")
        result = builder.build()

        first_child = result.children[0]
        assert not isinstance(first_child, Select)

    def test_widget_positioned_above_scatter(self):
        """Y-axis selector appears immediately above its scatter figure."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1")
        builder.add_scatter(y_column="HA", offered_columns=["HA", "fieldRA"], name="scatter2")
        result = builder.build()

        assert len(result.children) == 4
        assert isinstance(result.children[0], Select)
        assert hasattr(result.children[1], "x_range")
        assert isinstance(result.children[2], Select)
        assert hasattr(result.children[3], "x_range")

    def test_selector_updates_y_axis_label(self):
        """Y-axis selector callback updates the y-axis label."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1")
        result = builder.build()

        assert isinstance(result.children[0], Select)


# ============================================================================
# TimelineBuilder.build Tests
# ============================================================================


class TestBuild:
    """Tests for TimelineBuilder.build method."""

    def test_returns_bokeh_column_layout(self):
        """build returns a bokeh column layout."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        result = builder.build()
        assert isinstance(result, type(column()))

    def test_one_figure_per_scatter(self):
        """build creates one figure per scatter config."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")
        builder.add_scatter(y_column="fieldRA")
        result = builder.build()
        assert len(result.children) == 3

    def test_all_figures_share_same_x_range(self):
        """All figures share the same Range1d object."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")
        result = builder.build()
        x_ranges = [fig.x_range for fig in result.children]
        assert all(xr is x_ranges[0] for xr in x_ranges)

    def test_figure_has_datetime_axis(self):
        """Each figure has datetime x-axis type."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        result = builder.build()
        fig = result.children[0]
        assert isinstance(fig.xaxis[0].formatter, DatetimeTickFormatter)

    def test_datetime_tick_formatter_applied(self):
        """DatetimeTickFormatter with hours format is applied."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        result = builder.build()
        fig = result.children[0]
        x_axis = fig.xaxis[0]
        assert isinstance(x_axis.formatter, DatetimeTickFormatter)
        assert x_axis.formatter.hours == "%H:%M"

    def test_build_does_not_modify_elements(self):
        """build does not modify _elements list."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")
        elements_before = builder._elements.copy()
        builder.build()
        assert builder._elements == elements_before


# ============================================================================
# Build Mixed Elements Tests
# ============================================================================


class TestBuildMixedElements:
    """Tests for TimelineBuilder.build with mixed element types."""

    def test_scatter_and_visits_combined(self):
        """build overlays visits on scatter panels, no separate figures."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        result = builder.build()
        assert len(result.children) == 1
        assert len(result.children[0].renderers) >= 1

    def test_scatter_and_stripe_combined(self):
        """build handles scatter and color stripe together."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        assert len(result.children) == 2

    def test_visits_and_stripe_combined(self):
        """build with only visits and stripe produces the stripe panel."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        assert len(result.children) == 1

    def test_all_three_types_combined(self):
        """build handles scatter+visits+stripe with separate panels."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        assert len(result.children) == 2

    def test_order_matches_insertion_order(self):
        """Figure order matches insertion order of scatter/stripe elements."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="first")
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="second",
        )
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="third")
        result = builder.build()
        assert len(result.children) == 2

    def test_heights_respected_for_each_element(self):
        """Each element's height is respected."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1", height=150)
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1", height=30)
        builder.build()

        assert builder._plot_heights["scatter1"] == 150
        # visits do not store height (they are overlaid on scatter panels)
        assert builder._plot_heights.get("visits1") is None
        assert builder._plot_heights["stripe1"] == 30

    def test_datetime_formatter_on_all_figures(self):
        """DatetimeTickFormatter is applied to all figures."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        for fig in result.children:
            x_axis = fig.xaxis[0]
            assert isinstance(x_axis.formatter, DatetimeTickFormatter)

    def test_visits_overlaid_on_scatter_figure(self):
        """Visit data is overlaid as a scatter glyph on the scatter panel."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="main")
        builder.add_visits(
            pd.DataFrame(
                {
                    "observationStartMJD": [59999.0],
                    "altitude": [30.0],
                }
            ),
            label="visits1",
        )
        result = builder.build()
        scatter_fig = result.children[0]
        scatter_renderers = [r for r in scatter_fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) >= 1


# ============================================================================
# Color Stripe Rendering Tests
# ============================================================================


class TestColorStripeRendering:
    """Tests for color stripe rendering in build()."""

    def test_stripe_figure_has_rect_or_quad_glyph(self):
        """Stripe figure contains rect or quad glyph."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        stripe_fig = result.children[0]
        rect_renderers = [r for r in stripe_fig.renderers if isinstance(r.glyph, (Rect, Quad))]
        assert len(rect_renderers) >= 1

    def test_stripe_figure_has_no_y_axis(self):
        """Stripe figure has no y-axis (or y-axis is hidden)."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        stripe_fig = result.children[0]
        y_axis = stripe_fig.yaxis[0] if stripe_fig.yaxis else None
        if y_axis:
            assert not y_axis.visible or y_axis.axis_line_color is None

    def test_stripe_time_axis_formatted(self):
        """Stripe figure time axis uses DatetimeTickFormatter."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        stripe_fig = result.children[0]
        x_axis = stripe_fig.xaxis[0]
        assert isinstance(x_axis.formatter, DatetimeTickFormatter)


# ============================================================================
# Final Layout Assembly Tests
# ============================================================================


class TestFinalLayoutAssembly:
    """Tests for the final build layout with widgets and figures."""

    def test_layout_order_widgets_then_scatters_then_stripes(self):
        """Layout: visibility selector, then scatters, then stripes."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1")
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
            }
        )
        builder.add_visits(visits_df, label="visit1", show_visibility_toggle=True)
        builder.add_visit_visibility_selector()
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()

        assert isinstance(result.children[0], MultiChoice)
        assert isinstance(result.children[1], Select)

    def test_all_figures_share_single_range1d_x_range(self):
        """All figures share a single Range1d x-range object."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1")
        builder.add_scatter(y_column="HA", offered_columns=["HA", "fieldRA"], name="scatter2")
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()

        figures = [child for child in result.children if hasattr(child, "x_range")]
        x_ranges = [fig.x_range for fig in figures]
        assert all(xr is x_ranges[0] for xr in x_ranges)

    def test_heights_respected_for_all_elements(self):
        """All element heights are respected in final layout."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1", height=150
        )
        builder.add_scatter(y_column="HA", offered_columns=["HA"], name="scatter2", height=180)
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1", height=30)
        builder.build()

        assert builder._plot_heights["scatter1"] == 150
        assert builder._plot_heights["scatter2"] == 180
        assert builder._plot_heights["stripe1"] == 30

    def test_stripe_figures_have_no_y_axis(self):
        """Stripe figures have no visible y-axis."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude"], name="scatter1")
        builder.add_color_stripe(pd.Series([1.0, 2.0], index=[59999.0, 60000.0]), name="stripe1")
        result = builder.build()
        stripe_fig = result.children[-1]
        y_axis = stripe_fig.yaxis[0] if stripe_fig.yaxis else None
        if y_axis:
            assert not y_axis.visible or y_axis.axis_line_color is None

    def test_order_matches_insertion_order(self):
        """Figure order matches insertion order of elements."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", offered_columns=["altitude"], name="first")
        builder.add_color_stripe(pd.Series([1.0], index=[59999.0]), name="second")
        builder.add_scatter(y_column="HA", offered_columns=["HA"], name="third")
        result = builder.build()

        figures = [child for child in result.children if hasattr(child, "x_range")]
        assert len(figures) == 3


# ============================================================================
# CLI Tests
# ============================================================================


class TestCLI:
    """Tests for CLI functionality using click."""

    def test_cli_main_function_is_click_command(self):
        """main function is a click Command."""
        from schedview.plot.tlbuilder import main

        assert isinstance(main, click.Command)
        assert callable(main)

    def test_cli_with_click_runner(self):
        """CLI works with click CliRunner."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--output",
                "/tmp/test_output.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_date_required(self):
        """--date argument is required."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, ["--scatter", "altitude", "--output", "output.html"])
        assert result.exit_code != 0

    def test_cli_scatter_required(self):
        """--scatter argument is required."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, ["--date", "2025-06-15", "--output", "output.html"])
        assert result.exit_code != 0

    def test_cli_multiple_scatters(self):
        """CLI handles multiple --scatter arguments."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--scatter",
                "fieldRA",
                "--output",
                "output.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_accepts_visits_file(self):
        """CLI accepts --visits argument with file path."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        # Mock read_visits to return empty DataFrame so CLI succeeds
        with patch("schedview.collect.visits.read_visits") as mock_read:
            mock_read.return_value = pd.DataFrame()
            result = runner.invoke(
                main,
                [
                    "--date",
                    "2025-06-15",
                    "--scatter",
                    "altitude",
                    "--visits",
                    "/tmp/test_visits.parquet",
                    "--output",
                    "/tmp/cli_test.html",
                ],
            )
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

    def test_cli_accepts_multiple_visits_files(self):
        """CLI accepts multiple --visits arguments."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        # Mock read_visits to return empty DataFrame so CLI succeeds
        with patch("schedview.collect.visits.read_visits") as mock_read:
            mock_read.return_value = pd.DataFrame()
            result = runner.invoke(
                main,
                [
                    "--date",
                    "2025-06-15",
                    "--scatter",
                    "altitude",
                    "--visits",
                    "/tmp/visits1.parquet",
                    "--visits",
                    "/tmp/visits2.parquet",
                    "--output",
                    "/tmp/cli_test.html",
                ],
            )
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

    def test_cli_accepts_background_argument(self):
        """CLI accepts --background argument."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        # Mock read_visits and _sample_body_elevation for valid stripe
        with patch("schedview.collect.visits.read_visits") as mock_read:
            with patch("schedview.plot.tlbuilder._sample_body_elevation") as mock_bg:
                mock_read.return_value = pd.DataFrame()
                mock_bg.return_value = pd.Series(
                    [0.0, 10.0, 20.0, 10.0, 0.0],
                    index=[58000.0, 58000.1, 58000.2, 58000.3, 58000.4],
                )
                result = runner.invoke(
                    main,
                    [
                        "--date",
                        "2025-06-15",
                        "--scatter",
                        "altitude",
                        "--background",
                        "sun_elevation",
                        "--output",
                        "/tmp/cli_test.html",
                    ],
                )
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

    def test_cli_with_all_options(self):
        """CLI works with scatter, visits, and background together."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        # Mock read_visits and _sample_body_elevation for valid stripe
        with patch("schedview.collect.visits.read_visits") as mock_read:
            with patch("schedview.plot.tlbuilder._sample_body_elevation") as mock_bg:
                mock_read.return_value = pd.DataFrame()
                mock_bg.return_value = pd.Series(
                    [0.0, 10.0, 20.0, 10.0, 0.0],
                    index=[58000.0, 58000.1, 58000.2, 58000.3, 58000.4],
                )
                result = runner.invoke(
                    main,
                    [
                        "--date",
                        "2025-06-15",
                        "--scatter",
                        "altitude",
                        "--scatter",
                        "HA",
                        "--visits",
                        "/tmp/visits.parquet",
                        "--background",
                        "sun_elevation",
                        "--output",
                        "/tmp/cli_test.html",
                    ],
                )
        assert result.exit_code == 0, f"CLI failed with: {result.output}"

    def test_cli_with_enable_visibility_toggle_flag(self):
        """CLI with --enable-visibility-toggle flag."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--visits",
                "baseline",
                "--enable-visibility-toggle",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_num_scatter_option(self):
        """CLI with --num-scatter option creates multiple scatter plots."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--num-scatter",
                "2",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_scatter_height_option(self):
        """CLI with --scatter-height option sets scatter plot height."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter-height",
                "250",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_stripe_height_option(self):
        """CLI with --stripe-height option sets stripe plot height."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--stripe-height",
                "50",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_backward_compatible(self):
        """CLI works without new Stage C options (backward compatible)."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_y_columns_option(self):
        """CLI with --y-columns option offers columns for y-axis selector."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--y-columns",
                "altitude,HA,fieldRA",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_y_columns_multiple_scatters(self):
        """CLI with --y-columns applies same columns to all scatter plots."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--scatter",
                "fieldRA",
                "--y-columns",
                "altitude,HA,fieldRA",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_with_y_columns_merged_multiple(self):
        """CLI with multiple --y-columns options merges values together."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--scatter",
                "HA",
                "--scatter",
                "fieldRA",
                "--scatter",
                "fiveSigmaDepth",
                "--y-columns",
                "altitude,HA",
                "--y-columns",
                "fieldRA,fiveSigmaDepth",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_rejects_invalid_background_value(self):
        """CLI rejects invalid --background value with error."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--background",
                "invalid_type",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code != 0
        assert "invalid_type" in result.output or "Choice" in result.output

    def test_cli_accepts_sun_elevation_background(self):
        """CLI accepts sun_elevation as valid --background value."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--background",
                "sun_elevation",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_accepts_moon_elevation_background(self):
        """CLI accepts moon_elevation as valid --background value."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--background",
                "moon_elevation",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0

    def test_cli_accepts_multiple_background_types(self):
        """CLI accepts multiple --background options."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--date",
                "2025-06-15",
                "--scatter",
                "altitude",
                "--background",
                "sun_elevation",
                "--background",
                "moon_elevation",
                "--output",
                "/tmp/cli_test.html",
            ],
        )
        assert result.exit_code == 0


# ============================================================================
# Time Conversion Tests
# ============================================================================


class TestTimeConversion:
    """Tests for MJD to datetime64 conversion."""

    def test_time_conversion_via_astropy(self):
        """MJD conversion uses astropy.time.Time."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        x_range = builder._shared_x_range
        assert isinstance(x_range.start, np.datetime64)
        assert isinstance(x_range.end, np.datetime64)

    def test_datetime64_type_correct(self):
        """Converted values are datetime64 type."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        x_range = builder._shared_x_range
        assert np.issubdtype(type(x_range.start), np.datetime64) or isinstance(x_range.start, np.datetime64)
        assert np.issubdtype(type(x_range.end), np.datetime64) or isinstance(x_range.end, np.datetime64)


# ============================================================================
# Scatter Plot Rendering Tests
# ============================================================================


class TestScatterPlotRendering:
    """Tests for scatter plot rendering in build()."""

    def test_figure_has_scatter_glyph(self):
        """Figure contains scatter glyph renderer when visits are overlaid."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_visits(
            pd.DataFrame({"observationStartMJD": [59999.0], "altitude": [30.0]}),
            label="v1",
        )
        result = builder.build()
        fig = result.children[0]
        scatter_renderers = [r for r in fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) >= 1

    def test_scatter_glyph_x_field_is_time(self):
        """Scatter glyph uses 'time' as x field."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_visits(
            pd.DataFrame({"observationStartMJD": [59999.0], "altitude": [30.0]}),
            label="v1",
        )
        result = builder.build()
        fig = result.children[0]
        scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
        assert scatter_renderer.glyph.x == "time"

    def test_scatter_glyph_y_field_is_config_y_column(self):
        """Scatter glyph uses config.y_column as y field."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        builder.add_visits(
            pd.DataFrame({"observationStartMJD": [59999.0], "altitude": [30.0]}),
            label="v1",
        )
        result = builder.build()
        fig = result.children[0]
        scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
        assert scatter_renderer.glyph.y == "altitude"

    def test_duplicated_y_columns_use_same_field(self):
        """Each scatter panel with same y column renders that column."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="plot1")
        builder.add_scatter(y_column="altitude", name="plot2")
        builder.add_visits(
            pd.DataFrame({"observationStartMJD": [59999.0], "altitude": [30.0]}),
            label="v1",
        )
        result = builder.build()
        for fig in result.children:
            scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
            assert scatter_renderer.glyph.y == "altitude"


# ============================================================================
# Tooltips Tests
# ============================================================================


class TestScatterTooltips:
    """Tests for scatter plot tooltips functionality."""

    def test_add_scatter_stores_tooltips_in_config(self):
        """add_scatter stores tooltips in ScatterPlotConfig."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        tooltips = [("Time", "@time"), ("Altitude", "@altitude")]
        builder.add_scatter(y_column="altitude", tooltips=tooltips)

        config = builder._elements[0]
        assert isinstance(config, ScatterPlotConfig)
        assert config.tooltips == tuple(tooltips)

    def test_add_scatter_default_tooltips_is_none(self):
        """add_scatter defaults tooltips to None when not provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")

        config = builder._elements[0]
        assert config.tooltips is None

    def test_figure_has_hover_tool_with_explicit_tooltips(self):
        """Figure has HoverTool when tooltips are provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        tooltips = [("Time", "@time"), ("Altitude", "@altitude")]
        builder.add_scatter(y_column="altitude", tooltips=tooltips)
        result = builder.build()

        fig = result.children[0]
        hover_tools = [t for t in fig.tools if isinstance(t, HoverTool)]
        assert len(hover_tools) == 1
        assert hover_tools[0].tooltips == tooltips

    def test_figure_has_no_hover_tool_without_tooltips(self):
        """Figure has no HoverTool when tooltips are not provided."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude")
        result = builder.build()

        fig = result.children[0]
        hover_tools = [t for t in fig.tools if isinstance(t, HoverTool)]
        assert len(hover_tools) == 0

    def test_multiple_scatter_plots_with_tooltips(self):
        """Multiple scatter plots can each have their own tooltips."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(
            y_column="altitude",
            tooltips=[("Time", "@time"), ("Alt", "@altitude")],
            name="plot1",
        )
        builder.add_scatter(
            y_column="HA",
            tooltips=[("Time", "@time"), ("HA", "@HA")],
            name="plot2",
        )
        result = builder.build()

        # Find HoverTools in the figures
        hover_tools = []
        for child in result.children:
            if hasattr(child, "tools"):
                hover_tools.extend([t for t in child.tools if isinstance(t, HoverTool)])
        assert len(hover_tools) == 2

    def test_tooltips_work_with_visit_data(self):
        """Tooltips work correctly when visit data is overlaid."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        tooltips = [("Time", "@time"), ("Altitude", "@altitude"), ("Band", "@band")]
        builder.add_scatter(y_column="altitude", tooltips=tooltips)
        builder.add_visits(
            pd.DataFrame(
                {"observationStartMJD": [59999.0, 59999.1], "altitude": [30.0, 45.0], "band": ["g", "r"]}
            ),
            label="v1",
        )
        result = builder.build()

        fig = result.children[0]
        # Should have HoverTool
        hover_tools = [t for t in fig.tools if isinstance(t, HoverTool)]
        assert len(hover_tools) == 1
        assert hover_tools[0].tooltips == tooltips
        # Should also have scatter renderers from visits
        scatter_renderers = [r for r in fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) >= 1


# ============================================================================
# Y-Selector Column Filtering Tests
# ============================================================================


class TestYSelectorColumnFiltering:
    """Tests for filtering offered_columns against visit data availability."""

    def test_filters_offered_columns_to_available_visit_columns(self):
        """offered_columns are filtered to columns present in visit data."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "HA": [1.0, 2.0],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        # Offer columns including one that doesn't exist in visits
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "nonexistent_column"], name="scatter1"
        )

        config = builder._elements[0]
        # nonexistent_column should be filtered out
        assert "nonexistent_column" not in config.offered_columns
        assert "altitude" in config.offered_columns
        assert "HA" in config.offered_columns

    def test_preserves_all_offered_columns_when_no_visits(self):
        """When no visits present, all offered_columns are preserved."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        # No visits added
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "fieldRA"], name="scatter1"
        )

        config = builder._elements[0]
        # All offered columns should be preserved when no visits
        assert config.offered_columns == ("altitude", "HA", "fieldRA")

    def test_falls_back_to_first_available_column_when_y_column_unavailable(self):
        """y_column falls back to first available column if not in visits."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "HA": [1.0, 2.0],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        # Request y_column that doesn't exist in visits
        builder.add_scatter(
            y_column="nonexistent_column", offered_columns=["altitude", "HA"], name="scatter1"
        )

        config = builder._elements[0]
        # y_column should be set to first available column
        assert config.y_column == "altitude"
        assert "altitude" in config.offered_columns
        assert "HA" in config.offered_columns

    def test_keeps_y_column_when_it_is_available(self):
        """y_column is kept when it exists in visit data."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "HA": [1.0, 2.0],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "fieldRA"], name="scatter1"
        )

        config = builder._elements[0]
        # y_column should remain as specified since it's available
        assert config.y_column == "altitude"

    def test_filters_to_union_of_multiple_visit_sets(self):
        """offered_columns filtered to columns in at least one visit set."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df1 = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "HA": [1.0],
            }
        )
        visits_df2 = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [35.0],
                "fieldRA": [100.0],
            }
        )
        builder.add_visits(visits_df1, label="visits1")
        builder.add_visits(visits_df2, label="visits2")
        # Offered columns should include all columns from any visit set
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "fieldRA", "nonexistent"], name="scatter1"
        )

        config = builder._elements[0]
        # All columns from at least one visit set should be offered
        assert "altitude" in config.offered_columns  # In both
        assert "HA" in config.offered_columns  # Only in visits1
        assert "fieldRA" in config.offered_columns  # Only in visits2
        assert "nonexistent" not in config.offered_columns  # Not in any visit set

    def test_filtering_does_not_affect_nonexistent_y_column_with_empty_visits(self):
        """When visits have no rows, offered_columns are still preserved."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [],
                "altitude": [],
                "HA": [],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(y_column="altitude", offered_columns=["altitude", "HA"], name="scatter1")

        config = builder._elements[0]
        # Empty visits still have columns in the source, so filtering applies
        # But with empty data, the source should still have the columns
        assert "altitude" in config.offered_columns
        assert "HA" in config.offered_columns

    def test_selector_widget_uses_filtered_columns(self):
        """Y-axis selector widget uses filtered offered_columns."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "HA": [1.0, 2.0],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(
            y_column="altitude", offered_columns=["altitude", "HA", "nonexistent"], name="scatter1"
        )
        result = builder.build()

        # The selector should only have available columns
        selector = result.children[0]
        assert isinstance(selector, Select)
        assert "nonexistent" not in selector.options
        assert "altitude" in selector.options
        assert "HA" in selector.options

    def test_selector_value_is_valid_when_y_column_filtered_out(self):
        """Selector uses first offered column when y_column is filtered."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "HA": [1.0, 2.0],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        # Request nonexistent y_column, offered_columns has available ones
        builder.add_scatter(y_column="nonexistent", offered_columns=["altitude", "HA"], name="scatter1")
        result = builder.build()

        selector = result.children[0]
        assert isinstance(selector, Select)
        # y_column fell back to "altitude" (first available option)
        assert selector.value == "altitude"
        assert "altitude" in selector.options
        assert "HA" in selector.options


# ============================================================================
# add_color_legend Tests
# ============================================================================


class TestAddColorLegend:
    """Tests for TimelineBuilder.add_color_legend method."""

    def test_returns_self_for_chaining(self):
        """add_color_legend returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        result = builder.add_color_legend()
        assert result is builder

    def test_sets_needs_color_legend_flag(self):
        """add_color_legend sets the internal flag."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._needs_color_legend is False
        builder.add_color_legend()
        assert builder._needs_color_legend is True

    def test_legend_figure_appended_after_scatter(self):
        """Legend figure is appended after all other figures."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "band": ["g", "r"],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        result = builder.build()

        # Last child should be the legend figure (has a Legend layout)
        last_fig = result.children[-1]
        legends = [obj for obj in last_fig.center if isinstance(obj, Legend)]
        below_legends = last_fig.below
        assert len(below_legends) >= 1

    def test_legend_not_added_without_color_mapper(self):
        """No legend figure is appended when there are no visit sets."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        result = builder.build()

        # With no visits there is no color mapper, so no legend figure is added
        assert len(result.children) == 1

    def test_legend_contains_band_factors(self):
        """Legend items match the bands present in visit data."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0, 60001.0],
                "altitude": [30.0, 45.0, 60.0],
                "band": ["g", "r", "i"],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        result = builder.build()

        last_fig = result.children[-1]
        below = last_fig.below
        assert len(below) >= 1
        legend = below[0]
        assert isinstance(legend, Legend)
        legend_labels = [item.label["value"] for item in legend.items]
        assert "g" in legend_labels
        assert "r" in legend_labels
        assert "i" in legend_labels

    def test_legend_contains_other_for_overflow_values(self):
        """Legend includes 'other' when distinct values exceed palette size."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        num_visits = 20
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0 + i / 100 for i in range(num_visits)],
                "altitude": [30.0 + i for i in range(num_visits)],
                "visitId": [f"v{i}" for i in range(num_visits)],
            }
        )
        builder.map_colors("visitId")
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        result = builder.build()

        last_fig = result.children[-1]
        legend = last_fig.below[0]
        assert isinstance(legend, Legend)
        legend_labels = [item.label["value"] for item in legend.items]
        assert "other" in legend_labels

    def test_legend_is_horizontal(self):
        """Legend orientation is horizontal."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="visits1")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        result = builder.build()

        last_fig = result.children[-1]
        legend = last_fig.below[0]
        assert isinstance(legend, Legend)
        assert legend.orientation == "horizontal"

    def test_method_chaining_with_other_methods(self):
        """add_color_legend chains fluently with add_scatter and add_visits."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        result = (
            builder.add_visits(visits_df, label="v1")
            .add_scatter(y_column="altitude")
            .add_color_legend()
            .build()
        )
        assert result is not None


# ============================================================================
# add_marker_legend Tests
# ============================================================================


class TestAddMarkerLegend:
    """Tests for TimelineBuilder.add_marker_legend method."""

    def test_returns_self_for_chaining(self):
        """add_marker_legend returns self for method chaining."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        result = builder.add_marker_legend()
        assert result is builder

    def test_sets_needs_marker_legend_flag(self):
        """add_marker_legend sets the internal flag."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        assert builder._needs_marker_legend is False
        builder.add_marker_legend()
        assert builder._needs_marker_legend is True

    def test_marker_legend_figure_appended_after_scatter(self):
        """Marker legend figure is appended after all other figures."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0, 60000.0],
                "altitude": [30.0, 45.0],
                "band": ["g", "r"],
            }
        )
        builder.add_visits(visits_df, label="visits1", marker="triangle")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        # Last child should be the legend figure (has a Legend layout)
        last_fig = result.children[-1]
        below_legends = last_fig.below
        assert len(below_legends) >= 1

    def test_marker_legend_contains_visit_labels(self):
        """Marker legend items contain visit set labels."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="visits1", marker="triangle")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        last_fig = result.children[-1]
        below = last_fig.below
        assert len(below) >= 1
        legend = below[0]
        assert isinstance(legend, Legend)
        legend_labels = [item.label["value"] for item in legend.items]
        assert "visits1" in legend_labels

    def test_marker_legend_contains_multiple_visit_sets(self):
        """Marker legend includes all visit set labels when multiple visit sets."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df1 = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        visits_df2 = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [35.0],
                "band": ["r"],
            }
        )
        builder.add_visits(visits_df1, label="v1", marker="circle")
        builder.add_visits(visits_df2, label="v2", marker="square")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        last_fig = result.children[-1]
        below = last_fig.below
        legend = below[0]
        legend_labels = [item.label["value"] for item in legend.items]
        assert "v1" in legend_labels
        assert "v2" in legend_labels

    def test_marker_legend_with_custom_markers(self):
        """Marker legend respects custom marker types from add_visits."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="visits1", marker="triangle")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        last_fig = result.children[-1]
        below = last_fig.below
        legend = below[0]

        # Find the legend item for visits1 and check its renderer marker
        for item in legend.items:
            if item.label["value"] == "visits1":
                # Check that the renderer uses triangle marker
                renderer = item.renderers[0]
                assert renderer.glyph.marker == "triangle"
                break
        else:
            pytest.fail("Could not find 'visits1' in legend items")

    def test_marker_legend_not_added_without_visits(self):
        """No marker legend figure is appended when there are no visit sets."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        # With no visits, no legend figure is added
        assert len(result.children) == 1

    def test_color_and_marker_legend_together(self):
        """Both color and marker legends appear on same figure when both requested."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="visits1", marker="triangle")
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_color_legend()
        builder.add_marker_legend()
        result = builder.build()

        # Should have 2 children: scatter + legend figure
        assert len(result.children) == 2

        last_fig = result.children[-1]
        below = last_fig.below
        legend = below[0]
        legend_labels = [item.label["value"] for item in legend.items]

        # Should have both color (band) and marker (visit label) entries
        assert "g" in legend_labels
        assert "visits1" in legend_labels

    def test_method_chaining_with_other_methods(self):
        """add_marker_legend chains fluently with add_scatter and add_visits."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        result = (
            builder.add_visits(visits_df, label="v1", marker="circle")
            .add_scatter(y_column="altitude")
            .add_marker_legend()
            .build()
        )
        assert result is not None


# ============================================================================
# Auto-marker assignment Tests
# ============================================================================


class TestAutoMarkerAssignment:
    """Tests for automatic marker assignment in TimelineBuilder."""

    def test_auto_assigns_distinct_markers(self):
        """Auto-assigns distinct markers when none specified."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="v1")  # No marker - auto
        builder.add_visits(visits_df, label="v2")  # No marker - auto
        builder.add_visits(visits_df, label="v3")  # No marker - auto

        result = builder.build()

        markers = [d.marker for d in builder._visit_sets.values()]
        assert len(markers) == len(set(markers)), "All markers should be distinct"

    def test_auto_assigns_from_available_markers(self):
        """Auto-assigned markers are from AVAILABLE_MARKERS."""
        from schedview.plot.tlbuilder import AVAILABLE_MARKERS

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="v1")  # No marker - auto

        result = builder.build()

        for dataset in builder._visit_sets.values():
            if dataset.marker is not None:
                assert dataset.marker in AVAILABLE_MARKERS

    def test_auto_assign_skips_explicit_markers(self):
        """Auto-assign skips visit sets that have explicit markers."""
        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="v1", marker="circle")  # Explicit
        builder.add_visits(visits_df, label="v2")  # Auto
        builder.add_visits(visits_df, label="v3")  # Auto

        result = builder.build()

        # v1 should keep its explicit marker
        assert builder._visit_sets["v1"].marker == "circle"
        # v2 and v3 should have auto-assigned markers (not "circle")
        assert builder._visit_sets["v2"].marker is not None
        assert builder._visit_sets["v3"].marker is not None
        # And they should be different from each other
        assert builder._visit_sets["v2"].marker != builder._visit_sets["v3"].marker

    def test_auto_assignment_works_with_marker_legend(self):
        """Auto-assigned markers appear correctly in marker legend."""
        from bokeh.models import Legend

        builder = TimelineBuilder(DayObs.from_date("2025-06-15"))
        visits_df = pd.DataFrame(
            {
                "observationStartMJD": [59999.0],
                "altitude": [30.0],
                "band": ["g"],
            }
        )
        builder.add_visits(visits_df, label="v1")  # Auto
        builder.add_visits(visits_df, label="v2")  # Auto
        builder.add_scatter(y_column="altitude", name="scatter1")
        builder.add_marker_legend()
        result = builder.build()

        last_fig = result.children[-1]
        below = last_fig.below
        legend = below[0]
        legend_labels = [item.label["value"] for item in legend.items]

        assert "v1" in legend_labels
        assert "v2" in legend_labels
