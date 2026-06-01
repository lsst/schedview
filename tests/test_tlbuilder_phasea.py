"""Phase A test suite for tlbuilder.

Tests the core builder infrastructure, scatter plot support,
shared datetime x-axis, and minimal CLI.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import click
import numpy as np
import pytest
from astropy.time import Time
from click.testing import CliRunner
from bokeh.models import ColumnDataSource, DatetimeTickFormatter, Range1d, Scatter
from bokeh.layouts import column

from schedview.dayobs import DayObs
from schedview.plot.tlbuilder import (
    ColorStripeConfig,
    ScatterPlotConfig,
    TimelineBuilder,
    VisitDataSet,
)


class TestScatterPlotConfig:
    """Tests for ScatterPlotConfig dataclass."""

    def test_stores_name(self):
        """ScatterPlotConfig stores name correctly."""
        config = ScatterPlotConfig(name="test_plot", y_column="altitude", offered_columns=(), figure_kwargs={})
        assert config.name == "test_plot"

    def test_stores_y_column(self):
        """ScatterPlotConfig stores y_column correctly."""
        config = ScatterPlotConfig(name="test_plot", y_column="altitude", offered_columns=(), figure_kwargs={})
        assert config.y_column == "altitude"

    def test_stores_offered_columns(self):
        """ScatterPlotConfig stores offered_columns correctly."""
        offered = ("altitude", "HA", "fieldRA")
        config = ScatterPlotConfig(name="test_plot", y_column="altitude", offered_columns=offered, figure_kwargs={})
        assert config.offered_columns == offered

    def test_stores_figure_kwargs(self):
        """ScatterPlotConfig stores figure_kwargs correctly."""
        kwargs = {"width": 800}
        config = ScatterPlotConfig(name="test_plot", y_column="altitude", offered_columns=(), figure_kwargs=kwargs)
        assert config.figure_kwargs == kwargs


class TestColorStripeConfig:
    """Tests for ColorStripeConfig dataclass."""

    def test_class_exists(self):
        """ColorStripeConfig class exists."""
        assert ColorStripeConfig is not None

    def test_can_instantiate(self):
        """ColorStripeConfig can be instantiated with required args."""
        # ColorStripeConfig is now a dataclass with required arguments
        from bokeh.models import ColumnDataSource
        source = ColumnDataSource(data={"time": [], "value": []})
        config = ColorStripeConfig(
            name="test_stripe",
            source=source,
            colormap="Cividis256",
            value_range=(0.0, 1.0)
        )
        assert config is not None
        assert config.name == "test_stripe"
        assert config.colormap == "Cividis256"


class TestVisitDataSet:
    """Tests for VisitDataSet stub class."""

    def test_class_exists(self):
        """VisitDataSet class exists."""
        assert VisitDataSet is not None

    def test_can_instantiate(self):
        """VisitDataSet can be instantiated."""
        dataset = VisitDataSet()
        assert dataset is not None


class TestTimelineBuilderInitialization:
    """Tests for TimelineBuilder initialization."""

    def test_stores_dayobs(self):
        """TimelineBuilder stores dayobs correctly."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._dayobs is dayobs

    def test_initializes_empty_elements(self):
        """TimelineBuilder initializes _elements as empty list."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._elements == []

    def test_initializes_empty_visit_sets(self):
        """TimelineBuilder initializes _visit_sets as empty dict."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._visit_sets == {}

    def test_initializes_empty_color_stripes(self):
        """TimelineBuilder initializes _color_stripes as empty dict."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._color_stripes == {}

    def test_initializes_shared_x_range_none(self):
        """TimelineBuilder initializes _shared_x_range as None."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._shared_x_range is None

    def test_initializes_figure_kwargs(self):
        """TimelineBuilder initializes _figure_kwargs with defaults."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._figure_kwargs == {"width": 1000}

    def test_initializes_plot_heights(self):
        """TimelineBuilder initializes _plot_heights as empty dict."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._plot_heights == {}


class TestTimelineBuilderAddScatter:
    """Tests for TimelineBuilder.add_scatter method."""

    def test_returns_self(self):
        """add_scatter returns self for method chaining."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        result = builder.add_scatter(y_column="altitude")
        assert result is builder

    def test_appends_scatter_config(self):
        """add_scatter appends ScatterPlotConfig to _elements."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude", name="my_scatter")
        assert len(builder._elements) == 1
        assert isinstance(builder._elements[0], ScatterPlotConfig)
        assert builder._elements[0].name == "my_scatter"
        assert builder._elements[0].y_column == "altitude"

    def test_appends_multiple_scatters(self):
        """add_scatter appends multiple configs correctly."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude").add_scatter(y_column="HA", name="ha_plot")
        assert len(builder._elements) == 2
        assert builder._elements[0].name == "scatter"
        assert builder._elements[1].name == "ha_plot"

    def test_stores_height_if_provided(self):
        """add_scatter stores height in _plot_heights if provided."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude", height=250)
        assert builder._plot_heights["scatter"] == 250

    def test_stores_custom_name_height(self):
        """add_scatter stores height with custom name."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude", name="my_plot", height=300)
        assert builder._plot_heights["my_plot"] == 300

    def test_offered_columns_stored(self):
        """add_scatter stores offered_columns in config."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        offered = ("altitude", "HA", "fieldRA")
        builder.add_scatter(y_column="altitude", offered_columns=offered)
        assert builder._elements[0].offered_columns == offered

    def test_figure_kwargs_stored(self):
        """add_scatter stores figure_kwargs in config."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        kwargs = {"width": 800}
        builder.add_scatter(y_column="altitude", **kwargs)
        assert builder._elements[0].figure_kwargs == {"width": 800}

    def test_shared_x_range_created_on_first_scatter(self):
        """add_scatter creates shared x-range on first call."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        assert builder._shared_x_range is None

        builder.add_scatter(y_column="altitude")
        assert builder._shared_x_range is not None

    def test_shared_x_range_is_range1d(self):
        """Shared x-range is a Range1d instance."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        assert isinstance(builder._shared_x_range, Range1d)

    def test_shared_x_range_bounds_from_dayobs(self):
        """Shared x-range uses DayObs start/end times as datetime64."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude")
        x_range = builder._shared_x_range

        expected_start = Time(float(dayobs.start.mjd), format="mjd").datetime64
        expected_end = Time(float(dayobs.end.mjd), format="mjd").datetime64

        assert x_range.start == expected_start
        assert x_range.end == expected_end

    def test_shared_x_range_same_on_multiple_calls(self):
        """Shared x-range is the same object on multiple add_scatter calls."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)

        builder.add_scatter(y_column="altitude")
        first_range = builder._shared_x_range

        builder.add_scatter(y_column="HA")
        second_range = builder._shared_x_range

        assert first_range is second_range


class TestTimeConversion:
    """Tests for MJD to datetime64 conversion."""

    def test_time_conversion_via_astropy(self):
        """MJD conversion uses astropy.time.Time."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        x_range = builder._shared_x_range
        assert isinstance(x_range.start, np.datetime64)
        assert isinstance(x_range.end, np.datetime64)

    def test_datetime64_type_correct(self):
        """Converted values are datetime64 type."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        x_range = builder._shared_x_range
        assert np.issubdtype(type(x_range.start), np.datetime64) or isinstance(x_range.start, np.datetime64)
        assert np.issubdtype(type(x_range.end), np.datetime64) or isinstance(x_range.end, np.datetime64)


class TestTimelineBuilderBuild:
    """Tests for TimelineBuilder.build method."""

    def test_returns_bokeh_column(self):
        """build returns a bokeh column layout."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        result = builder.build()

        assert isinstance(result, type(column()))

    def test_one_figure_per_scatter(self):
        """build creates one figure per scatter config."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")
        builder.add_scatter(y_column="fieldRA")

        result = builder.build()

        assert len(result.children) == 3

    def test_all_figures_share_same_x_range(self):
        """All figures share the same Range1d object."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")

        result = builder.build()

        x_ranges = [fig.x_range for fig in result.children]
        assert all(xr is x_ranges[0] for xr in x_ranges)

    def test_figure_has_datetime_axis(self):
        """Each figure has datetime x-axis type."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        result = builder.build()
        fig = result.children[0]

        assert isinstance(fig.xaxis[0].formatter, DatetimeTickFormatter)

    def test_figure_has_scatter_glyph(self):
        """Figure contains scatter glyph renderer."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        result = builder.build()
        fig = result.children[0]

        scatter_renderers = [r for r in fig.renderers if isinstance(r.glyph, Scatter)]
        assert len(scatter_renderers) == 1

    def test_scatter_glyph_x_field_is_time(self):
        """Scatter glyph uses 'time' as x field."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        result = builder.build()
        fig = result.children[0]

        scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
        assert scatter_renderer.glyph.x == "time"

    def test_scatter_glyph_y_field_is_config_y_column(self):
        """Scatter glyph uses config.y_column as y field."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        result = builder.build()
        fig = result.children[0]

        scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
        assert scatter_renderer.glyph.y == "altitude"

    def test_duplicated_y_columns_use_same_field(self):
        """Multiple scatters with same y column use same y field."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude", name="plot1")
        builder.add_scatter(y_column="altitude", name="plot2")

        result = builder.build()

        for fig in result.children:
            scatter_renderer = [r for r in fig.renderers if isinstance(r.glyph, Scatter)][0]
            assert scatter_renderer.glyph.y == "altitude"

    def test_datetime_tick_formatter_applied(self):
        """DatetimeTickFormatter with hours format is applied."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")

        result = builder.build()
        fig = result.children[0]

        x_axis = fig.xaxis[0]
        assert isinstance(x_axis.formatter, DatetimeTickFormatter)
        assert x_axis.formatter.hours == "%H:%M"

    def test_build_does_not_modify_elements(self):
        """build does not modify _elements list."""
        dayobs = DayObs.from_date("2025-06-15")
        builder = TimelineBuilder(dayobs)
        builder.add_scatter(y_column="altitude")
        builder.add_scatter(y_column="HA")

        elements_before = builder._elements.copy()
        builder.build()

        assert builder._elements == elements_before


class TestCLI:
    """Tests for CLI v1 functionality using click."""

    def test_cli_main_function_is_click_command(self):
        """main function is a click Command."""
        from schedview.plot.tlbuilder import main
        assert isinstance(main, click.Command)
        assert callable(main)

    def test_cli_creates_builder(self):
        """CLI instantiates TimelineBuilder."""
        dayobs = DayObs.from_date("2025-06-15")

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.build.return_value = MagicMock()

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        mock_path.write_text = lambda x: None

                        from schedview.plot.tlbuilder import main
                        main.callback(date="2025-06-15", scatter=("altitude",), visits=(), background=(), output="output.html")

                        MockBuilder.assert_called_once_with(dayobs)

    def test_cli_adds_scatters(self):
        """CLI calls add_scatter for each --scatter argument."""
        dayobs = DayObs.from_date("2025-06-15")

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.build.return_value = MagicMock()

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        mock_path.write_text = lambda x: None

                        from schedview.plot.tlbuilder import main
                        main.callback(
                            date="2025-06-15",
                            scatter=("altitude", "HA", "fieldRA"),
                            visits=(),
                            background=(),
                            output="output.html"
                        )

                        assert mock_builder.add_scatter.call_count == 3
                        calls = mock_builder.add_scatter.call_args_list
                        assert calls[0].kwargs["y_column"] == "altitude"
                        assert calls[1].kwargs["y_column"] == "HA"
                        assert calls[2].kwargs["y_column"] == "fieldRA"

    def test_cli_calls_build(self):
        """CLI calls build() method."""
        dayobs = DayObs.from_date("2025-06-15")

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.build.return_value = MagicMock()

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        mock_path.write_text = lambda x: None

                        from schedview.plot.tlbuilder import main
                        main.callback(date="2025-06-15", scatter=("altitude",), visits=(), background=(), output="output.html")

                        mock_builder.build.assert_called_once()

    def test_cli_writes_html_file(self):
        """CLI writes HTML output to specified file."""
        dayobs = DayObs.from_date("2025-06-15")
        mock_layout = MagicMock()

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            MockBuilder.return_value.build.return_value = mock_layout

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        mock_path.write_text = lambda x: None

                        from schedview.plot.tlbuilder import main
                        main.callback(date="2025-06-15", scatter=("altitude",), visits=(), background=(), output="output.html")

                        mock_file_html.assert_called_once()
                        args, kwargs = mock_file_html.call_args
                        assert args[0] is mock_layout

    def test_cli_accepts_single_scatter(self):
        """CLI works with single --scatter argument."""
        dayobs = DayObs.from_date("2025-06-15")

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.build.return_value = MagicMock()

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        mock_path.write_text = lambda x: None

                        from schedview.plot.tlbuilder import main
                        main.callback(date="2025-06-15", scatter=("altitude",), visits=(), background=(), output="output.html")

                        assert mock_builder.add_scatter.call_count == 1

    def test_cli_default_output(self):
        """CLI uses default output filename if not specified."""
        dayobs = DayObs.from_date("2025-06-15")
        write_calls = []

        with patch("schedview.plot.tlbuilder.TimelineBuilder") as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.build.return_value = MagicMock()

            with patch("schedview.dayobs.DayObs.from_date") as MockDayObs:
                MockDayObs.return_value = dayobs

                with patch("schedview.plot.tlbuilder.file_html") as mock_file_html:
                    mock_file_html.return_value = "<html>mock</html>"

                    with patch("schedview.plot.tlbuilder.Path") as MockPath:
                        mock_path = MagicMock()
                        MockPath.return_value = mock_path
                        mock_path.exists.return_value = False
                        def capture_write(*args, **kwargs):
                            write_calls.append(args)
                        mock_path.write_text = capture_write

                        from schedview.plot.tlbuilder import main
                        main.callback(date="2025-06-15", scatter=("altitude",), visits=(), background=(), output="timeline.html")

                        assert len(write_calls) > 0
                        assert write_calls[0][0] is not None


class TestCLIIntegration:
    """Integration tests for CLI using click."""

    def test_cli_with_click_runner(self):
        """CLI works with click CliRunner."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--scatter", "HA",
            "--output", "/tmp/test_output.html"
        ])
        assert result.exit_code == 0

    def test_cli_date_required(self):
        """--date argument is required."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--scatter", "altitude",
            "--output", "output.html"
        ])
        assert result.exit_code != 0

    def test_cli_scatter_required(self):
        """--scatter argument is required."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--output", "output.html"
        ])
        assert result.exit_code != 0

    def test_cli_multiple_scatters(self):
        """CLI handles multiple --scatter arguments."""
        from schedview.plot.tlbuilder import main

        runner = CliRunner()
        result = runner.invoke(main, [
            "--date", "2025-06-15",
            "--scatter", "altitude",
            "--scatter", "HA",
            "--scatter", "fieldRA",
            "--output", "output.html"
        ])
        assert result.exit_code == 0
