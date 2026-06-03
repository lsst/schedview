"""Timeline Builder"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Self

import click
import numpy as np
import pandas as pd
from astropy.time import Time
from bokeh.embed import file_html
from bokeh.layouts import column
from bokeh.models import (
    CategoricalColorMapper,
    Column,
    ColumnDataSource,
    CustomJS,
    DatetimeTickFormatter,
    HoverTool,
    Legend,
    LegendItem,
    LinearColorMapper,
    MultiChoice,
    Plot,
    Range1d,
    Select,
)
from bokeh.core.enums import MarkerType
from bokeh.palettes import Colorblind
from bokeh.plotting import figure

from schedview.dayobs import DayObs
from schedview.plot.colors import PLOT_BAND_COLORS

# Available marker types for automatic assignment
AVAILABLE_MARKERS = list(MarkerType)
DEFAULT_MARKER = "circle"
# Shared borders so scatter and stripe plot areas are pixel-aligned on both sides.
_SHARED_MIN_BORDER_LEFT = 60
_SHARED_MIN_BORDER_RIGHT = 10


def _find_time_column(df: pd.DataFrame, time_column: str | None = None) -> str:
    """Find the column containing MJD timestamps in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to search for a time column.
    time_column : str or None, optional
        Explicit column name to use. If provided, this column is used
        directly without heuristic search.

    Returns
    -------
    str
        The name of the column containing MJD timestamps.

    Notes
    -----
    When time_column is not provided, the method uses a heuristic:
    1. Look for columns containing 'mjd' (case-insensitive)
    2. If no match found, use the first column as the time column
    """
    if time_column is not None:
        return time_column

    # Heuristic: look for columns with 'mjd' in name or 'time_mjd'
    for col in df.columns:
        if "mjd" in col.lower() or col == "time_mjd":
            return col

    # Use first column as time
    return df.columns[0]


@dataclass
class ScatterPlotConfig:
    """Configuration for a scatter plot element.

    Parameters
    ----------
    name : str
        Identifier for this scatter plot.
    y_column : str
        Column name to use for y-axis data.
    offered_columns : Iterable[str]
        Columns available for y-axis selection.
    figure_kwargs : dict
        Additional arguments for bokeh.plotting.figure.
    tooltips : tuple or None
        Hover tooltips for the scatter plot.
    """

    name: str
    y_column: str
    offered_columns: tuple[str, ...]
    figure_kwargs: dict
    tooltips: tuple | None = None


@dataclass
class ColorStripeConfig:
    """Configuration for a color stripe element.

    Parameters
    ----------
    name : str
        Identifier for this color stripe.
    source : ColumnDataSource
        Data source with time and value columns.
    colormap : str
        Bokeh colormap name to use.
    value_range : tuple[float, float]
        Min and max values for colormap scaling.
    """

    name: str
    source: ColumnDataSource
    colormap: str
    value_range: tuple[float, float]


@dataclass
class VisitDataSet:
    """Data set for visit plots.

    Parameters
    ----------
    source : ColumnDataSource
        Data source with time and y-axis data.
    label : str
        Identifier for this visit set.
    alpha : float
        Opacity value for the glyphs.
    marker : str
        Marker type for scatter glyphs. If not specified (None), a distinct
        marker will be automatically assigned during build() to help
        differentiate visit sets in the legend.
    """

    source: ColumnDataSource | None = None
    label: str = ""
    alpha: float = 1.0
    marker: str | None = None
    show_visibility_toggle: bool = True


class TimelineBuilder:
    """Build interactive timeline visualizations.

    Parameters
    ----------
    dayobs : DayObs
        The day of observing to visualize.
    """

    def __init__(self, dayobs: DayObs) -> None:
        """Initialize the TimelineBuilder.

        Parameters
        ----------
        dayobs : DayObs
            The day of observing to visualize.
        """
        self._dayobs = dayobs
        self._elements: list[ScatterPlotConfig | ColorStripeConfig] = []
        self._visit_sets: dict[str, VisitDataSet] = {}
        self._color_column: str = "band"
        start_time = Time(float(dayobs.sunset.mjd), format="mjd").datetime64
        end_time = Time(float(dayobs.sunrise.mjd), format="mjd").datetime64
        self._shared_x_range = Range1d(start=start_time, end=end_time)
        self._figure_kwargs: dict = {"width": 1000}
        self._plot_heights: dict[str, int] = {}
        self._visibility_selector: MultiChoice | None = None
        self._needs_visit_visibility_selector: bool = False
        self._needs_color_legend: bool = False
        self._needs_marker_legend: bool = False
        self._assigned_markers: list[str] = []

    def _get_available_columns(self) -> set[str]:
        """Get columns available in visit data sources.

        Returns
        -------
        set[str]
            Column names available in at least one visit set source.
        """
        available: set[str] = set()
        for visit_set in self._visit_sets.values():
            if visit_set.source is not None:
                source_cols = set(visit_set.source.data.keys())
                available |= source_cols  # Union of all columns from all visit sets
        return available

    def add_scatter(
        self,
        y_column: str,
        offered_columns: Iterable[str] = (),
        name: str = "scatter",
        height: int | None = None,
        tooltips: list | None = None,
        **figure_kwargs,
    ) -> Self:
        """Add a scatter plot to the timeline.

        Parameters
        ----------
        y_column : str
            The initial column to plot on the y-axis.
        offered_columns : Iterable[str], optional
            Columns to offer in the y-axis selector dropdown.
            If provided, columns are filtered to those present in at least
            one visit set source. If no visit sets are present, all offered
            columns are kept.
        name : str, optional
            Identifier for this scatter plot.
        height : int, optional
            Height of the plot in pixels.
        tooltips : list or None, optional
            Hover tooltips
        **figure_kwargs
            Additional arguments to pass to bokeh.plotting.figure.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Store height if provided
        if height is not None:
            self._plot_heights[name] = height

        # Filter offered_columns to only include those present in visit data
        # If no visit sets, keep all offered columns (backward compatible)
        offered_list = list(offered_columns)
        if offered_list:
            available = self._get_available_columns()
            if available:
                # Filter to only columns that exist in at least one visit set.
                filtered_offered = [col for col in offered_list if col in available]
                # If y_column is not available, use the first available.
                if y_column not in available and filtered_offered:
                    y_column = filtered_offered[0]
                offered_list = filtered_offered
            # If no available columns from visits, keep all offered columns
            # (this preserves behavior when no visits are present)

        config = ScatterPlotConfig(
            name=name,
            y_column=y_column,
            offered_columns=tuple(offered_list),
            figure_kwargs=figure_kwargs,
            tooltips=tuple(tooltips) if tooltips is not None else None,
        )
        self._elements.append(config)
        return self

    def add_visits(
        self,
        visits: pd.DataFrame,
        label: str = "visits",
        alpha: float = 1.0,
        marker: str | None = None,
        show_visibility_toggle: bool = True,
        time_column: str | None = None,
    ) -> Self:
        """Add a visit plot to the timeline.

        Parameters
        ----------
        visits : pd.DataFrame
            DataFrame from `schedview.collect.visits.read_visits()`.
        label : str, optional
            Identifier for this visit set.
        alpha : float, optional
            Opacity for the visit glyphs.
        marker : str or None, optional
            Marker type for scatter glyphs. If ``None`` (default), a distinct
            marker will be automatically assigned to help differentiate visit
            sets in the legend.
        show_visibility_toggle : bool, optional
            Whether to show visibility toggle.
        time_column : str or None, optional
            Column name containing MJD timestamps. If not provided,
            defaults to 'observationStartMJD' or uses heuristic to find
            a column containing 'mjd'.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Convert MJD to datetime64
        if len(visits) > 0:
            mjd_col = _find_time_column(visits, time_column)
            mjd_times = visits[mjd_col].values
            times = Time(mjd_times, format="mjd").datetime64
        else:
            times = np.array([], dtype="datetime64[us]")

        # Build source with all data columns for scatter y_column access.
        source_data: dict = {"time": times}
        for col in visits.columns:
            if col != time_column:
                source_data[col] = visits[col].values

        source = ColumnDataSource(data=source_data)

        self._visit_sets[label] = VisitDataSet(
            source=source,
            label=label,
            alpha=alpha,
            marker=marker,
            show_visibility_toggle=show_visibility_toggle,
        )
        # Visits are overlaid on scatter panels; they don't create figures.
        return self

    def add_color_stripe(
        self,
        data: pd.Series | pd.DataFrame,
        name: str,
        height: int | None = None,
        colormap: str = "Cividis256",
        value_range: tuple[float, float] | None = None,
        value_column: str = "value",
        time_column: str | None = None,
    ) -> Self:
        """Add a color stripe for continuous time-series data.

        Parameters
        ----------
        data : pd.Series or pd.DataFrame
            Time-series data. If Series, indexed by MJD.
            If DataFrame, must have a column with MJD timestamps.
        name : str
            Identifier for this stripe.
        height : int, optional
            Height of the stripe in pixels. Default is 40.
        colormap : str, optional
            Bokeh colormap name. Default is "Cividis256".
        value_range : tuple[float, float], optional
            Min and max values for colormap scaling.
            Auto-computed if not provided.
        value_column : str, optional
            Column name containing values in a DataFrame.
        time_column : str or None, optional
            Column name containing MJD timestamps in a DataFrame.
            If provided, this column is used directly. Otherwise,
            the method uses a heuristic to detect the time column
            (column with 'mjd' in name or 'time_mjd', or first column).

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        stripe_height = height if height is not None else 40
        self._plot_heights[name] = stripe_height

        # Process data and convert MJD to datetime64
        if isinstance(data, pd.Series):
            # Series indexed by MJD
            mjd_times = np.array(data.index)
            values = data.values
        else:
            # DataFrame with MJD column
            mjd_col = _find_time_column(data, time_column)
            mjd_times = data[mjd_col].values
            values = data[value_column].values

        # Check for empty data before datetime conversion
        if len(values) == 0:
            raise ValueError(
                f"Color stripe '{name}' has no data. " "Cannot auto-compute value_range with empty data."
            )

        # Convert MJD to datetime64
        times = Time(mjd_times, format="mjd").datetime64

        # Auto-compute value range if not provided
        if value_range is None:
            # Use nanmin/nanmax for NaN-safe calculation
            # Filter out NaN and infinite values for range computation
            finite_values = values[np.isfinite(values)]
            if len(finite_values) == 0:
                raise ValueError(
                    f"Color stripe '{name}' has no finite values. "
                    "Cannot auto-compute value_range with all-NaN or empty data."
                )
            value_range = (float(np.nanmin(finite_values)), float(np.nanmax(finite_values)))

        # Compute adjacent rectangle widths for continuous coverage.
        # Bokeh datetime axes use milliseconds since epoch.
        if len(times) >= 2:
            # Calculate half-gaps between adjacent midpoints
            half_gaps = np.diff(times) / 2
            # Extend left edge (first half-gap) and right edge (last half-gap)
            left = np.concatenate([[half_gaps[0]], half_gaps])
            right = np.concatenate([half_gaps, [half_gaps[-1]]])
            # Compute widths in milliseconds
            widths = ((left + right) / np.timedelta64(1, "ms")).tolist()
        else:
            # Single point: 1-hour wide in milliseconds
            widths = [3_600_000.0] * len(times) if len(times) > 0 else []

        # Create data source with time, value, and width
        source = ColumnDataSource(data={"time": times, "value": values, "width": widths})

        # Create color stripe config
        stripe_config = ColorStripeConfig(
            name=name,
            source=source,
            colormap=colormap,
            value_range=value_range,
        )

        # Add to elements
        self._elements.append(stripe_config)

        return self

    def add_visit_visibility_selector(self) -> Self:
        """Add a MultiChoice widget to toggle visibility of visit sets.

        Records intent to include a visibility selector widget that allows
        users to show/hide different visit data sets.
        The selector is created during build() with current visit sets.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        self._needs_visit_visibility_selector = True
        return self

    def map_colors(self, column: str) -> Self:
        """Set the column to use for color encoding visit points.

        This setting applies to all scatter plots in the timeline.

        Parameters
        ----------
        column : str
            Column name to use for color encoding. Default is "band".
            When "band", uses the standard LSST band palette (PLOT_BAND_COLORS).
            For any other column, uses Bokeh's "Colorblind" palette.
            If there are more distinct values than palette size, least common
            values are combined into an "other" bin.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        self._color_column = column
        return self

    def add_color_legend(self) -> Self:
        """Add a color legend panel at the bottom of the timeline.

        The legend maps each color value to the label from the column set by
        `map_colors()` (default ``"band"``).  Values collapsed into the
        ``"other"`` bin are shown with the label ``"other"``.

        The legend is rendered as a dedicated figure appended after all other
        elements and is only materialised during `build()`, so it always
        reflects the final color mapping.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        self._needs_color_legend = True
        return self

    def add_marker_legend(self) -> Self:
        """Add a marker legend panel at the bottom of the timeline.

        The legend maps each marker shape to the label of the visit set
        added via `add_visits()`.  This legend appears next to the color
        legend at the bottom of the visualization, attached to the same
        ``height=1`` figure.

        The marker legend is only materialised during `build()`, so it always
        reflects the final visit sets.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        self._needs_marker_legend = True
        return self

    def _build_color_legend_figure(
        self, color_mapper: CategoricalColorMapper | None
    ) -> Plot | None:
        """Build a thin figure containing horizontal Bokeh Legends for color and marker.

        Parameters
        ----------
        color_mapper : CategoricalColorMapper or None
            The mapper whose factors and palette are used to populate the color legend.
            If ``None``, no color legend is created.

        Returns
        -------
        Plot or None
            A short Bokeh figure with horizontal legends and no axes, or ``None``
            if neither color legend nor marker legend is needed.
        """
        # Determine if we need any legend
        needs_color = self._needs_color_legend and color_mapper is not None
        needs_marker = self._needs_marker_legend and len(self._visit_sets) > 0

        if not needs_color and not needs_marker:
            return None

        fig_width = self._figure_kwargs.get("width", 1000)

        fig = figure(
            width=fig_width,
            height=1,
            toolbar_location=None,
            x_axis_type=None,
            y_axis_type=None,
            x_range=(0, 1),
            y_range=(0, 1),
        )
        fig.xgrid.visible = False
        fig.ygrid.visible = False
        fig.outline_line_color = None

        items: list[LegendItem] = []

        # Build color legend items first
        if needs_color:
            for factor, color in zip(color_mapper.factors, color_mapper.palette):
                renderer = fig.scatter(
                    x=[0.5],
                    y=[0.5],
                    fill_color=color,
                    line_color=None,
                    size=12,
                )
                renderer.visible = False
                items.append(LegendItem(label=str(factor), renderers=[renderer]))

        # Build marker legend items (attached to same figure)
        if needs_marker:
            # Create invisible scatter renderers for each visit set's marker
            for label, visit_set in self._visit_sets.items():
                renderer = fig.scatter(
                    x=[0.5],
                    y=[0.5],
                    marker=visit_set.marker,
                    fill_color="black",
                    line_color="black",
                    size=12,
                )
                renderer.visible = False
                items.append(LegendItem(label=label, renderers=[renderer]))

        legend = Legend(items=items, orientation="horizontal", location="center")
        fig.add_layout(legend, "below")

        return fig

    def _assign_markers(self) -> None:
        """Assign distinct markers to visit sets that don't have one specified.

        Iterates through all visit sets and assigns a distinct marker from
        AVAILABLE_MARKERS to any visit set with marker=None. Marks visited
        markers to ensure uniqueness.

        Notes
        -----
        If there are more visit sets than available markers, the method
        cycles through the available markers.
        """
        # Collect visit sets that need marker assignment
        unmarked_sets: list[tuple[str, VisitDataSet]] = []
        used_markers: set[str] = set()

        for label, dataset in self._visit_sets.items():
            if dataset.marker is None:
                unmarked_sets.append((label, dataset))
            else:
                used_markers.add(dataset.marker)

        # Assign distinct markers to unmarked visit sets
        for label, dataset in unmarked_sets:
            # Find an unused marker
            for marker in AVAILABLE_MARKERS:
                if marker not in used_markers:
                    dataset.marker = marker
                    used_markers.add(marker)
                    break
            else:
                # All markers exhausted, cycle back to first available
                dataset.marker = AVAILABLE_MARKERS[0]

    def build(self) -> Column:
        """Build and return the final Bokeh layout.

        Creates scatter plots, visit plots, and color stripes with optional
        interactive widgets for y-axis selection and visit visibility toggling.

        Returns
        -------
        column
            Bokeh column layout containing all figures and widgets.
        """
        layout_components = []
        # Track visit renderers for visibility toggling
        visit_renderers: dict[str, list] = {}

        # Assign distinct markers to visit sets that don't have one specified
        self._assign_markers()

        # Build color mapper once; mutates visit sources for "other" binning
        color_mapper = self._build_color_mapper()

        # Process elements in insertion order
        for element in self._elements:
            if isinstance(element, ScatterPlotConfig):
                # Create scatter figure with renderer tracking
                fig = self._create_scatter_figure(
                    element, color_mapper=color_mapper, visit_renderers=visit_renderers
                )
                # Create y-axis selector if multiple offered_columns
                # (placed after figure since figure is needed for callback)
                y_selector = self._create_scatter_y_selector(element, fig)
                if y_selector is not None:
                    # Wrap selector and figure in a Column for centering
                    # Column with sizing_mode='stretch_width' makes children full width
                    # align='center' centers the selector (which has fixed width)
                    layout_components.append(
                        Column(y_selector, fig, sizing_mode="stretch_width", align="center")
                    )
                else:
                    layout_components.append(fig)
            elif isinstance(element, ColorStripeConfig):
                # No y-axis selector for stripes
                fig = self._create_stripe_figure(element)
                layout_components.append(fig)

        # Create visibility selector at build time with current visit sets
        if self._needs_visit_visibility_selector:
            # Build list of visit set labels with visibility toggle enabled
            options = [label for label, dataset in self._visit_sets.items() if dataset.show_visibility_toggle]

            # Only create selector if there are visit sets with toggle.
            if options:
                self._visibility_selector = MultiChoice(
                    value=options,
                    options=options,
                    width=400,
                )

                # Build visit set info with renderer references.
                visit_sets_for_callback = {}
                for label, dataset in self._visit_sets.items():
                    if dataset.show_visibility_toggle:
                        # Get renderers; empty if none tracked.
                        renderers = visit_renderers.get(label, [])
                        visit_sets_for_callback[label] = {"renderers": renderers}

                if visit_sets_for_callback:
                    # Create callback to toggle visit renderer visibility.
                    callback_code = """
                        const selected_labels = this.value;
                        for (const [label, visit_info] of Object.entries(visit_sets)) {
                            const isVisible = selected_labels.includes(label);
                            for (const renderer of visit_info.renderers) {
                                renderer.visible = isVisible;
                                renderer.change.emit();
                            }
                        }
                    """

                    self._visibility_selector.js_on_change(
                        "value", CustomJS(args={"visit_sets": visit_sets_for_callback}, code=callback_code)
                    )

                # Add visibility selector to layout (first, before figures)
                layout_components.insert(0, self._visibility_selector)

        # Append legend figure (with color and/or marker legend) at the bottom
        legend_fig = self._build_color_legend_figure(color_mapper)
        if legend_fig is not None:
            layout_components.append(legend_fig)

        return column(*layout_components)

    def _create_scatter_y_selector(self, config: ScatterPlotConfig, fig: Plot) -> Select | None:
        """Create a y-axis selector widget for a scatter plot.

        Creates a Select widget with offered_columns as options, centered
        above the scatter figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the scatter plot.
        fig : Plot
            The scatter figure this selector controls.

        Returns
        -------
        Select or None
            The y-axis selector widget if multiple offered_columns, else None.
        """
        # Only create selector if multiple columns offered.
        if len(config.offered_columns) <= 1:
            return None

        # Create the Select widget with offered columns.
        # Use first offered column if y_column is not available.
        initial_value = config.y_column
        if config.y_column not in config.offered_columns:
            initial_value = config.offered_columns[0] if config.offered_columns else None
        selector = Select(
            value=initial_value,
            options=list(config.offered_columns),
            width=200,
            align="center",
        )

        # Create CustomJS callback to update y-field.
        # Bokeh 3.x requires {field: new_y} for column references;
        # a plain string is treated as a constant value.
        callback_code = """
            const new_y = cb_obj.value;
            for (const renderer of fig.renderers) {
                if (renderer.glyph && renderer.glyph.type === 'Scatter') {
                    renderer.glyph.y = {field: new_y};
                    renderer.glyph.change.emit();
                }
            }
            for (const axis of fig.axes) {
                if (axis.type === 'LinearAxis') {
                    axis.axis_label = new_y;
                }
            }
            fig.change.emit();
        """

        selector.js_on_change("value", CustomJS(args={"fig": fig}, code=callback_code))

        return selector

    def _build_color_mapper(self) -> CategoricalColorMapper | None:
        """Build and return the CategoricalColorMapper for visit color encoding.

        Mutates visit sources to add an ``<column>_color`` field when the
        ``"other"`` bin is needed (more distinct values than palette size).

        Returns
        -------
        CategoricalColorMapper or None
            The mapper, or ``None`` when no visit sets contain the color column.
        """
        color_col_name, all_values = self._get_color_column_data()
        if all_values is None:
            return None

        if self._color_column == "band":
            existing_bands = [b for b in all_values if b in PLOT_BAND_COLORS]
            if not existing_bands:
                return None
            return CategoricalColorMapper(
                factors=existing_bands,
                palette=[PLOT_BAND_COLORS[b] for b in existing_bands],
            )

        # Non-band column: use Colorblind palette
        palette_size = len(Colorblind[8])
        if len(all_values) <= palette_size:
            return CategoricalColorMapper(
                factors=all_values,
                palette=list(Colorblind[8][: len(all_values)]),
            )

        # Too many values — collapse least-common into "other"
        value_counts: dict[str, int] = {}
        for visit_set in self._visit_sets.values():
            if visit_set.source is not None and color_col_name in visit_set.source.data:
                for val in visit_set.source.data[color_col_name]:
                    value_counts[val] = value_counts.get(val, 0) + 1

        sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        top_values = [v[0] for v in sorted_values[:palette_size]]
        palette = list(Colorblind[8][: len(top_values)]) + ["#888888"]

        mapper = CategoricalColorMapper(
            factors=top_values + ["other"],
            palette=palette,
        )

        # Remap source data: values not in top_values become "other"
        for visit_set in self._visit_sets.values():
            if visit_set.source is not None and color_col_name in visit_set.source.data:
                orig = visit_set.source.data[color_col_name]
                visit_set.source.data[f"{color_col_name}_color"] = [
                    v if v in top_values else "other" for v in orig
                ]

        return mapper

    def _get_color_column_data(self) -> tuple[str, list[str] | None]:
        """Get the color column data from all visit sets.

        Returns a tuple of (column_name, all_unique_values) where all_unique_values
        is the list of all distinct values seen across all visit sets for the
        color column, or None if the color column doesn't exist in any visit set.
        """
        all_values: list[str] = []
        for visit_set in self._visit_sets.values():
            if visit_set.source is not None and self._color_column in visit_set.source.data:
                col_data = visit_set.source.data[self._color_column]
                for val in col_data:
                    if val not in all_values:
                        all_values.append(val)
        if len(all_values) == 0:
            return (self._color_column, None)
        return (self._color_column, all_values)

    def _create_scatter_figure(
        self,
        config: ScatterPlotConfig,
        color_mapper: CategoricalColorMapper | None = None,
        visit_renderers: dict[str, list] | None = None,
    ) -> Plot:
        """Create a scatter plot figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the scatter plot.
        color_mapper : CategoricalColorMapper or None
            Pre-built color mapper (from ``_build_color_mapper``).  When
            ``None``, visit points are rendered in the default blue.
        visit_renderers : dict[str, list] | None
            Maps visit set labels to renderer lists for visibility toggling.

        Returns
        -------
        figure
            Bokeh figure with scatter glyph.
        """
        # Get height from plot_heights, default to 200
        height = self._plot_heights.get(config.name, 200)

        # Combine default figure kwargs with config kwargs
        fig_kwargs = {
            "width": 1000,
            "x_axis_type": "datetime",
            "toolbar_location": "above",
            "min_border_left": _SHARED_MIN_BORDER_LEFT,
            "min_border_right": _SHARED_MIN_BORDER_RIGHT,
        }
        if self._figure_kwargs:
            fig_kwargs.update(self._figure_kwargs)
        if config.figure_kwargs:
            fig_kwargs.update(config.figure_kwargs)
        fig_kwargs["height"] = height
        fig_kwargs["x_range"] = self._shared_x_range

        fig = figure(**fig_kwargs)

        # Add hover tooltips if specified
        if config.tooltips is not None:
            fig.add_tools(HoverTool(tooltips=list(config.tooltips)))

        color_col_name = self._color_column

        # Overlay visit sets onto this scatter panel using y_column.
        for visit_set in self._visit_sets.values():
            if config.y_column not in visit_set.source.data:
                continue

            # Determine color field based on mapper
            if color_mapper is not None:
                # Use the color column with the mapper
                color_field = f"{color_col_name}_color" if f"{color_col_name}_color" in visit_set.source.data else color_col_name
                renderer = fig.scatter(
                    x="time",
                    y=config.y_column,
                    source=visit_set.source,
                    size=5,
                    marker=visit_set.marker,
                    fill_color={"field": color_field, "transform": color_mapper},
                    line_color={"field": color_field, "transform": color_mapper},
                    fill_alpha=visit_set.alpha,
                    line_alpha=visit_set.alpha,
                )
            else:
                # No color mapping - use default blue
                renderer = fig.scatter(
                    x="time",
                    y=config.y_column,
                    source=visit_set.source,
                    size=5,
                    marker=visit_set.marker,
                    fill_color="#1f77b4",
                    line_color="#1f77b4",
                    fill_alpha=visit_set.alpha,
                    line_alpha=visit_set.alpha,
                )

            # Track renderer for visibility toggling.
            # Initialize list for each visit set if visit_renderers provided.
            if visit_renderers is not None:
                if visit_set.label not in visit_renderers:
                    visit_renderers[visit_set.label] = []
                visit_renderers[visit_set.label].append(renderer)

        # Apply datetime tick formatter
        fig.xaxis[0].formatter = DatetimeTickFormatter(hours="%H:%M")

        return fig

    def _create_stripe_figure(self, config: ColorStripeConfig) -> Plot:
        """Create a color stripe figure.

        Parameters
        ----------
        config : ColorStripeConfig
            Configuration for the color stripe.

        Returns
        -------
        figure
            Bokeh figure with color stripe glyphs.
        """
        # Get height from plot_heights, default to 40
        height = self._plot_heights.get(config.name, 40)

        # Create figure with no y-axis and explicit y_range.
        fig_kwargs = {
            "width": 1000,
            "x_axis_type": "datetime",
            "height": height,
            "y_range": (0, 1),  # Explicit y_range for single horizontal stripe
            "y_axis_type": None,  # No y-axis type
            "x_range": self._shared_x_range,
            "toolbar_location": None,
            "min_border_left": _SHARED_MIN_BORDER_LEFT,
            "min_border_right": _SHARED_MIN_BORDER_RIGHT,
        }
        if self._figure_kwargs:
            fig_kwargs.update(self._figure_kwargs)

        fig = figure(**fig_kwargs)

        # Get colormap from bokeh palettes
        import bokeh.palettes as palettes

        if hasattr(palettes, config.colormap):
            palette = getattr(palettes, config.colormap)
        else:
            # Default to Viridis256
            palette = palettes.Viridis256

        # Create linear color mapper.
        color_mapper = LinearColorMapper(
            palette=palette,
            low=config.value_range[0],
            high=config.value_range[1],
        )

        # Add stripe as rect glyphs
        # Rect uses y as center, height as total height
        # Set y=0.5 with height=1 to span from y=0 to y=1 (matching y_range)
        fig.rect(
            x="time",
            y=0.5,
            width="width",  # Width is in the data source
            height=1,
            source=config.source,
            fill_color={"field": "value", "transform": color_mapper},
            line_color=None,
        )

        # Apply datetime tick formatter
        fig.xaxis[0].formatter = DatetimeTickFormatter(hours="%H:%M")

        return fig


def build_timeline(dayobs: DayObs, scatter_columns: list[str]) -> Column:
    """Build a timeline with scatter plots.

    Parameters
    ----------
    dayobs : DayObs
        The day of observing to visualize.
    scatter_columns : list[str]
        List of column names to plot as scatter plots.

    Returns
    -------
    column
        Bokeh column layout with scatter plots.
    """
    builder = TimelineBuilder(dayobs)

    for column_name in scatter_columns:
        builder.add_scatter(y_column=column_name)

    return builder.build()


def _sample_body_elevation(body_name: str, dayobs: DayObs) -> pd.Series:
    """Sample a celestial body's elevation from sunset to sunrise.

    Parameters
    ----------
    body_name : str
        The name of the body to sample ("sun" or "moon").
    dayobs : DayObs
        The observing day.

    Returns
    -------
    pd.Series
        Series of elevation angles in degrees, indexed by MJD.
    """
    from astropy.coordinates import AltAz, get_body

    mjds = np.arange(float(dayobs.sunset.mjd), float(dayobs.sunrise.mjd), 1 / 24)
    times_ap = Time(mjds, format="mjd")
    altaz_frame = AltAz(location=dayobs.location, obstime=times_ap)
    altaz = get_body(body_name, times_ap).transform_to(altaz_frame)
    return pd.Series(altaz.alt.deg, index=mjds)


@click.command(help="Build timeline visualizations for Rubin Observatory observing nights.")
@click.option(
    "--date",
    required=True,
    help="Date of the observing night (YYYY-MM-DD format).",
)
@click.option(
    "--scatter",
    multiple=True,
    required=True,
    help="Column name to plot as a scatter plot (can be specified multiple times).",
)
@click.option(
    "--visits",
    multiple=True,
    required=False,
    help=(
        "Visit source: 'baseline', an SQLite3 filename, or any valid " "visit_source string for read_visits."
    ),
)
@click.option(
    "--background",
    multiple=True,
    required=False,
    type=click.Choice(["sun_elevation", "moon_elevation"], case_sensitive=False),
    help="Background stripe type: sun_elevation, moon_elevation.",
)
@click.option(
    "--output",
    default="timeline.html",
    help="Output HTML file path (default: timeline.html).",
)
@click.option(
    "--enable-visibility-toggle",
    is_flag=True,
    default=False,
    help="Enable visit set visibility toggle widget.",
)
@click.option(
    "--num-scatter",
    type=int,
    default=None,
    help="Number of scatter plots to create (duplicates the first scatter column).",
)
@click.option(
    "--scatter-height",
    type=int,
    default=None,
    help="Height for scatter plots in pixels.",
)
@click.option(
    "--stripe-height",
    type=int,
    default=None,
    help="Height for color stripe plots in pixels.",
)
@click.option(
    "--y-columns",
    multiple=True,
    required=False,
    help="Comma-separated list of columns to offer in y-axis selector for scatter plots.",
)
def main(
    date: str,
    scatter: tuple[str, ...],
    visits: tuple[str, ...],
    background: tuple[str, ...],
    output: str,
    enable_visibility_toggle: bool,
    num_scatter: int | None,
    scatter_height: int | None,
    stripe_height: int | None,
    y_columns: tuple[str, ...],
) -> None:
    """CLI entry point."""
    from schedview.collect.visits import read_visits

    # Create DayObs from date
    dayobs = DayObs.from_date(date)

    # Build the timeline
    builder = TimelineBuilder(dayobs)

    # Parse y-columns option (supports both single comma-separated value
    # and multiple --y-columns options that are merged together)
    y_columns_offered = ()
    if y_columns:
        # Merge --y-columns, splitting comma-separated values
        all_columns = []
        for y_cols in y_columns:
            all_columns.extend(c.strip() for c in y_cols.split(",") if c.strip())
        y_columns_offered = tuple(all_columns)

    if num_scatter is not None and num_scatter > 0:
        # Create num_scatter scatter plots using first scatter column.
        first_column = scatter[0] if scatter else "altitude"
        for i in range(num_scatter):
            name = f"scatter_{i+1}"
            builder.add_scatter(
                y_column=first_column,
                offered_columns=y_columns_offered,
                name=name,
                height=scatter_height,
            )
    else:
        # Add scatter plots for each provided column.
        for column_name in scatter:
            name = column_name
            builder.add_scatter(
                y_column=column_name,
                offered_columns=y_columns_offered,
                name=name,
                height=scatter_height,
            )

    # Add visits
    for visit_source in visits:
        # Load visits via read_visits
        # visit_source can be "baseline", an SQLite3 file, or valid source
        visits_df = read_visits(dayobs, str(visit_source))

        # Generate label from visit source
        # For "baseline", use "baseline" as label
        # For files, use the filename stem
        if visit_source == "baseline":
            label = "baseline"
        else:
            label = Path(visit_source).stem

        builder.add_visits(visits_df, label=label, show_visibility_toggle=True)

    # Add background stripes.
    for bg_type in background:
        if bg_type == "sun_elevation":
            sun_data = _sample_body_elevation("sun", dayobs)
            stripe_h = stripe_height if stripe_height is not None else 100
            builder.add_color_stripe(sun_data, name="sun_elevation", height=stripe_h)

        elif bg_type == "moon_elevation":
            moon_data = _sample_body_elevation("moon", dayobs)
            stripe_h = stripe_height if stripe_height is not None else 100
            builder.add_color_stripe(moon_data, name="moon_elevation", height=stripe_h)

        else:
            # This should never happen since click.Choice validates the value
            raise click.BadParameter(f"Unknown background type: {bg_type}")

    # Add visibility toggle if enabled
    if enable_visibility_toggle:
        builder.add_visit_visibility_selector()

    # Always include legends when visits are present
    builder.add_color_legend()
    builder.add_marker_legend()

    # Build the layout
    layout = builder.build()

    # Write to HTML file
    output_path = Path(output)
    html = file_html(layout)
    output_path.write_text(html)


if __name__ == "__main__":
    main()
