"""Timeline Builder - Phase B implementation.

Core builder infrastructure, scatter plot support,
visit plots, color stripes, shared datetime x-axis,
and CLI v2.
"""

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
    ColumnDataSource,
    CustomJS,
    DatetimeTickFormatter,
    LinearColorMapper,
    MultiChoice,
    Range1d,
    Scatter,
    Select,
)
from bokeh.plotting import figure

from schedview.dayobs import DayObs


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
    """

    name: str
    y_column: str
    offered_columns: tuple[str, ...]
    figure_kwargs: dict


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
        Marker type for scatter glyphs.
    color_by_band : bool
        Whether to color points by band.
    visible : bool
        Whether the visit set is visible by default.
    """

    source: ColumnDataSource | None = None
    label: str = ""
    alpha: float = 1.0
    marker: str = "circle"
    color_by_band: bool = True
    visible: bool = True
    show_visibility_toggle: bool = True


# Band colors mapping (LSST ugrizy)
BAND_COLORS = {
    "u": "#3B449B",  # blue
    "g": "#20B2AA",  # light sea green
    "r": "#FF4500",  # orange red
    "i": "#FFD700",  # gold
    "z": "#8B4513",  # saddle brown
    "y": "#800080",  # purple
}


class TimelineBuilder:
    """Build interactive timeline visualizations.

    Phase A provides:
    - Core builder infrastructure
    - Scatter plot support
    - Shared datetime x-axis
    - Correct MJD to datetime64 conversion
    - Vertical stacking of scatter figures
    - Minimal CLI v1

    Phase B adds:
    - Visit plots via add_visits()
    - Color stripes via add_color_stripe()
    - Mixed-element stacked layouts
    - CLI v2 with --visits and --background options

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
        self._color_stripes: dict[str, ColorStripeConfig] = {}
        self._shared_x_range: Range1d | None = None
        self._figure_kwargs: dict = {"width": 1000}
        self._plot_heights: dict[str, int] = {}
        self._visibility_selector: MultiChoice | None = None
        # Track y-axis selectors for each scatter plot
        self._scatter_y_selectors: dict[str, Select] = {}

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
        name : str, optional
            Identifier for this scatter plot.
        height : int, optional
            Height of the plot in pixels.
        tooltips : list or None, optional
            Hover tooltips (not implemented in Phase A).
        **figure_kwargs
            Additional arguments to pass to bokeh.plotting.figure.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Initialize shared x-range on first scatter
        if self._shared_x_range is None:
            # Convert DayObs start/end MJD to datetime64
            start_time = Time(float(self._dayobs.start.mjd), format="mjd").datetime64
            end_time = Time(float(self._dayobs.end.mjd), format="mjd").datetime64
            self._shared_x_range = Range1d(start=start_time, end=end_time)

        # Store height if provided
        if height is not None:
            self._plot_heights[name] = height

        config = ScatterPlotConfig(
            name=name,
            y_column=y_column,
            offered_columns=tuple(offered_columns),
            figure_kwargs=figure_kwargs,
        )
        self._elements.append(config)
        return self

    def add_visits(
        self,
        visits: pd.DataFrame,
        label: str = "visits",
        alpha: float = 1.0,
        marker: str = "circle",
        color_by_band: bool = True,
        show_visibility_toggle: bool = True,
        time_column: str = "observationStartMJD",
        **scatter_kwargs,
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
        marker : str, optional
            Marker type for scatter glyphs.
        color_by_band : bool, optional
            Whether to color points by band column.
        show_visibility_toggle : bool, optional
            Whether to show visibility toggle (not implemented in Phase B).
        time_column : str, optional
            Column name containing MJD timestamps.
        **scatter_kwargs
            Additional arguments, including `height` for plot height.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Initialize shared x-range if not already done
        if self._shared_x_range is None:
            start_time = Time(float(self._dayobs.start.mjd), format="mjd").datetime64
            end_time = Time(float(self._dayobs.end.mjd), format="mjd").datetime64
            self._shared_x_range = Range1d(start=start_time, end=end_time)

        # Store height if provided
        if "height" in scatter_kwargs:
            self._plot_heights[label] = scatter_kwargs["height"]

        # Convert MJD to datetime64
        if len(visits) > 0:
            mjd_times = visits[time_column].values
            times = Time(mjd_times, format="mjd").datetime64
        else:
            times = np.array([], dtype="datetime64[us]")

        # Build source with ALL data columns so any scatter y_column can use the data.
        source_data: dict = {"time": times}
        for col in visits.columns:
            if col != time_column:
                source_data[col] = visits[col].values

        # Add band colors
        if color_by_band and "band" in visits.columns:
            bands = visits["band"].values
            colors = [BAND_COLORS.get(b, "#888888") for b in bands]
            source_data["color"] = colors
        else:
            source_data["color"] = ["#1f77b4"] * len(visits) if len(visits) > 0 else []

        source = ColumnDataSource(data=source_data)

        self._visit_sets[label] = VisitDataSet(
            source=source,
            label=label,
            alpha=alpha,
            marker=marker,
            color_by_band=color_by_band,
            visible=True,
            show_visibility_toggle=show_visibility_toggle,
        )
        # Visits are overlaid on scatter panels — they do not create their own figures.
        return self

    def add_color_stripe(
        self,
        data: pd.Series | pd.DataFrame,
        name: str,
        height: int | None = None,
        colormap: str = "Cividis256",
        value_range: tuple[float, float] | None = None,
        value_column: str = "value",
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
            Height of the stripe in pixels. Default is 20.
        colormap : str, optional
            Bokeh colormap name. Default is "Cividis256".
        value_range : tuple[float, float], optional
            Min and max values for colormap scaling.
            Auto-computed if not provided.
        value_column : str, optional
            Column name containing values in a DataFrame.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Initialize shared x-range if not already done
        if self._shared_x_range is None:
            start_time = Time(float(self._dayobs.start.mjd), format="mjd").datetime64
            end_time = Time(float(self._dayobs.end.mjd), format="mjd").datetime64
            self._shared_x_range = Range1d(start=start_time, end=end_time)

        # Store height (default 20 px)
        # Default height for color stripes is 40 px (was 20 px) for better visibility
        stripe_height = height if height is not None else 40
        self._plot_heights[name] = stripe_height

        # Process data and convert MJD to datetime64
        if isinstance(data, pd.Series):
            # Series indexed by MJD
            mjd_times = np.array(data.index)
            values = data.values
        else:
            # DataFrame with MJD column (we need to detect which column is time)
            # Assume the first numeric column with 'mjd' in name or 'time'
            mjd_col = None
            for col in data.columns:
                if "mjd" in col.lower() or col == "time_mjd":
                    mjd_col = col
                    break
            if mjd_col is None:
                # Use first column as time
                mjd_col = data.columns[0]
            mjd_times = data[mjd_col].values
            values = data[value_column].values

        # Convert MJD to datetime64
        times = Time(mjd_times, format="mjd").datetime64

        # Auto-compute value range if not provided
        if value_range is None:
            value_range = (float(np.min(values)), float(np.max(values)))

        # Compute adjacent rectangle widths for continuous coverage.
        # Bokeh datetime axes store values in milliseconds since epoch, so widths
        # must also be in milliseconds.
        widths = []
        if len(times) >= 2:
            for i in range(len(times)):
                if i == 0:
                    mid_to_next = (times[i + 1] - times[i]) / 2
                    width = float(mid_to_next / np.timedelta64(1, 'ms'))
                elif i == len(times) - 1:
                    mid_to_prev = (times[i] - times[i - 1]) / 2
                    width = float(mid_to_prev / np.timedelta64(1, 'ms'))
                else:
                    mid_to_prev = (times[i] - times[i - 1]) / 2
                    mid_to_next = (times[i + 1] - times[i]) / 2
                    width = float((mid_to_prev + mid_to_next) / np.timedelta64(1, 'ms'))
                widths.append(width)
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
        self._color_stripes[name] = stripe_config

        # Add to elements
        self._elements.append(stripe_config)

        return self

    def add_visit_visibility_selector(self) -> Self:
        """Add a MultiChoice widget to toggle visibility of visit sets.

        Creates a MultiChoice widget that allows users to show/hide
        different visit data sets that were added with show_visibility_toggle=True.

        Returns
        -------
        Self
            Returns self for method chaining.
        """
        # Get list of visit set labels that should be visible by default
        # Only include visits with show_visibility_toggle=True
        options = [
            label for label, dataset in self._visit_sets.items()
            if dataset.visible and dataset.show_visibility_toggle
        ]

        self._visibility_selector = MultiChoice(
            value=options,
            options=options,
            width=400,
        )

        return self

    def build(self) -> column:
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

        # Process elements in insertion order
        for element in self._elements:
            if isinstance(element, ScatterPlotConfig):
                # Create scatter figure with renderer tracking
                fig = self._create_scatter_figure(element, visit_renderers=visit_renderers)
                layout_components.append(fig)
                # Create y-axis selector if multiple offered_columns
                # (placed after figure since figure is needed for callback)
                y_selector = self._create_scatter_y_selector(element, fig)
                if y_selector is not None:
                    layout_components.insert(len(layout_components) - 1, y_selector)
            elif isinstance(element, ColorStripeConfig):
                # No y-axis selector for stripes
                fig = self._create_stripe_figure(element)
                layout_components.append(fig)

        # Wire up visibility selector callback with tracked renderers
        if self._visibility_selector is not None:
            # Build visit set info with actual renderer references
            visit_sets_for_callback = {}
            for label, dataset in self._visit_sets.items():
                if dataset.visible and dataset.show_visibility_toggle:
                    # Get renderers for this visit set, or empty list if none tracked
                    renderers = visit_renderers.get(label, [])
                    visit_sets_for_callback[label] = {
                        "source": dataset.source,
                        "visible": dataset.visible,
                        "renderers": renderers
                    }

            if visit_sets_for_callback:
                # Create CustomJS callback to toggle visibility of visit renderers
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
                    'value',
                    CustomJS(
                        args={'visit_sets': visit_sets_for_callback},
                        code=callback_code
                    )
                )

            # Add visibility selector to layout (first, before figures)
            layout_components.insert(0, self._visibility_selector)

        return column(*layout_components)

    def _create_scatter_y_selector(self, config: ScatterPlotConfig, fig: figure) -> Select | None:
        """Create a y-axis selector widget for a scatter plot.

        Creates a Select widget with offered_columns as options.
        The widget is positioned directly above its corresponding scatter figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the scatter plot.
        fig : figure
            The scatter figure this selector controls.

        Returns
        -------
        Select or None
            The y-axis selector widget if multiple offered_columns, else None.
        """
        # Only create selector if multiple columns offered
        if len(config.offered_columns) <= 1:
            return None

        # Create the Select widget with offered columns
        selector = Select(
            title="Y-Axis:",
            value=config.y_column,
            options=list(config.offered_columns),
            width=200,
        )

        # Create CustomJS callback to update y-field and y-axis label
        callback_code = """
            const new_y = cb_obj.value;
            // Find the glyph renderer and update its y field
            for (const renderer of fig.renderers) {
                if (renderer.glyph && renderer.glyph.type === 'Scatter') {
                    renderer.glyph.y = new_y;
                    renderer.change.emit();
                }
            }
            // Update y-axis label
            for (const axis of fig.axes) {
                if (axis.type === 'LinearAxis') {
                    axis.axis_label = new_y;
                    axis.change.emit();
                }
            }
        """

        selector.js_on_change(
            'value',
            CustomJS(
                args={'fig': fig},
                code=callback_code
            )
        )

        return selector

    def _create_scatter_figure(self, config: ScatterPlotConfig, visit_renderers: dict[str, list] | None = None) -> figure:
        """Create a scatter plot figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the scatter plot.
        visit_renderers : dict[str, list] | None
            Dictionary mapping visit set labels to lists of renderer references.
            If provided, renderers will be added to these lists for visibility toggling.

        Returns
        -------
        figure
            Bokeh figure with scatter glyph.
        """
        # Get height from plot_heights, default to 200
        height = self._plot_heights.get(config.name, 200)

        # Combine default figure kwargs with config kwargs
        fig_kwargs = {"width": 1000, "x_axis_type": "datetime"}
        if self._figure_kwargs:
            fig_kwargs.update(self._figure_kwargs)
        if config.figure_kwargs:
            fig_kwargs.update(config.figure_kwargs)
        fig_kwargs["height"] = height
        fig_kwargs["x_range"] = self._shared_x_range

        fig = figure(**fig_kwargs)

        # Overlay all visit sets onto this scatter panel using the panel's y_column.
        for visit_set in self._visit_sets.values():
            if config.y_column not in visit_set.source.data:
                continue
            color = "color" if visit_set.color_by_band else "#1f77b4"
            renderer = fig.scatter(
                x="time",
                y=config.y_column,
                source=visit_set.source,
                size=5,
                marker=visit_set.marker,
                fill_color=color,
                line_color=color,
                fill_alpha=visit_set.alpha,
                line_alpha=visit_set.alpha,
                legend_label=visit_set.label,
            )

            # Track this renderer for visibility toggling
            # Always initialize the list for each visit set label if visit_renderers is provided
            if visit_renderers is not None:
                if visit_set.label not in visit_renderers:
                    visit_renderers[visit_set.label] = []
                visit_renderers[visit_set.label].append(renderer)

        # Apply datetime tick formatter
        fig.xaxis[0].formatter = DatetimeTickFormatter(hours="%H:%M")

        return fig

    def _create_stripe_figure(self, config: ColorStripeConfig) -> figure:
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

        # Create figure with no y-axis
        # Use explicit y_range to ensure the rectangles are visible
        # Set y_axis_type=None and y_axis_location=None to hide y-axis completely
        fig_kwargs = {
            "width": 1000,
            "x_axis_type": "datetime",
            "height": height,
            "y_range": (0, 1),  # Explicit y_range for single horizontal stripe
            "y_axis_type": None,  # No y-axis type
            "x_range": self._shared_x_range,
            "toolbar_location": None,
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

        # Create linear color mapper
        color_mapper = LinearColorMapper(palette=palette, low=config.value_range[0], high=config.value_range[1])

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


def build_timeline(dayobs: DayObs, scatter_columns: list[str]) -> column:
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


@click.command(
    help="Build timeline visualizations for Rubin Observatory observing nights."
)
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
    help="Visit source: 'baseline' for the default baseline, an SQLite3 filename, or any valid visit_source string accepted by read_visits.",
)
@click.option(
    "--background",
    multiple=True,
    required=False,
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
) -> None:
    """CLI entry point."""
    import pandas as pd

    from schedview.collect.visits import read_visits

    # Create DayObs from date
    dayobs = DayObs.from_date(date)

    # Build the timeline
    builder = TimelineBuilder(dayobs)

    # Handle scatter plots - either use provided columns or num_scatter option
    if num_scatter is not None and num_scatter > 0:
        # Create num_scatter scatter plots, all using the first scatter column
        first_column = scatter[0] if scatter else "altitude"
        for i in range(num_scatter):
            name = f"scatter_{i+1}"
            builder.add_scatter(y_column=first_column, name=name, height=scatter_height)
    else:
        # Add scatter plots for each provided column
        for column_name in scatter:
            name = column_name
            builder.add_scatter(y_column=column_name, name=name, height=scatter_height)

    # Add visits
    for visit_source in visits:
        # Load visits data using read_visits
        # visit_source can be "baseline", an SQLite3 filename, or any valid source
        visits_df = read_visits(dayobs, str(visit_source))

        # Generate label from visit source
        # For "baseline", use "baseline" as label
        # For files, use the filename stem
        if visit_source == "baseline":
            label = "baseline"
        else:
            label = Path(visit_source).stem

        builder.add_visits(visits_df, label=label, show_visibility_toggle=True)

    # Add background stripes
    for bg_type in background:
        if bg_type == "sun_elevation":
            # Compute sun elevation throughout the day
            times = []
            elevations = []

            # Sample sun position every hour
            start_mjd = float(dayobs.start.mjd)
            end_mjd = float(dayobs.end.mjd)

            from astropy.coordinates import get_body, AltAz
            from astropy.time import Time

            # Generate hourly samples
            current_mjd = start_mjd
            while current_mjd <= end_mjd:
                times.append(current_mjd)
                # Get sun position at this time
                sun = get_body("sun", Time(current_mjd, format="mjd"))

                # Create AltAz frame with location and obstime, then transform
                altaz_frame = AltAz(location=dayobs.location, obstime=Time(current_mjd, format="mjd"))
                sun_altaz = sun.transform_to(altaz_frame)
                elevations.append(sun_altaz.alt.deg)
                current_mjd += 1 / 24  # One hour

            sun_data = pd.Series(elevations, index=times)
            builder.add_color_stripe(sun_data, name="sun_elevation", height=stripe_height if stripe_height is not None else 100)

        elif bg_type == "moon_elevation":
            # Compute moon elevation throughout the day
            times = []
            elevations = []

            # Sample moon position every hour
            start_mjd = float(dayobs.start.mjd)
            end_mjd = float(dayobs.end.mjd)

            from astropy.coordinates import get_body, AltAz
            from astropy.time import Time

            # Generate hourly samples
            current_mjd = start_mjd
            while current_mjd <= end_mjd:
                times.append(current_mjd)
                # Get moon position at this time
                moon = get_body("moon", Time(current_mjd, format="mjd"))

                # Create AltAz frame with location and obstime, then transform
                altaz_frame = AltAz(location=dayobs.location, obstime=Time(current_mjd, format="mjd"))
                moon_altaz = moon.transform_to(altaz_frame)
                elevations.append(moon_altaz.alt.deg)
                current_mjd += 1 / 24  # One hour

            moon_data = pd.Series(elevations, index=times)
            builder.add_color_stripe(moon_data, name="moon_elevation", height=stripe_height if stripe_height is not None else 100)

        else:
            # Unknown background type - could be extended in future
            pass

    # Add visibility toggle if enabled
    if enable_visibility_toggle:
        builder.add_visit_visibility_selector()

    # Build the layout
    layout = builder.build()

    # Write to HTML file
    output_path = Path(output)
    html = file_html(layout)
    output_path.write_text(html)


if __name__ == "__main__":
    main()
