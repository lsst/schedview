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
    DatetimeTickFormatter,
    LinearColorMapper,
    Range1d,
    Scatter,
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

        # Create data source
        source_data = {"time": times}

        # Get y-column data (default to altitude if it exists)
        if "altitude" in visits.columns:
            source_data["altitude"] = visits["altitude"].values
        elif len(visits.columns) > 1:
            # Use first non-time column
            y_col = [c for c in visits.columns if c != time_column][0]
            source_data[y_col] = visits[y_col].values

        # Add band colors if band column exists and color_by_band is True
        if color_by_band and "band" in visits.columns:
            bands = visits["band"].values
            colors = [BAND_COLORS.get(b, "#888888") for b in bands]
            source_data["color"] = colors
        else:
            # Use default color
            source_data["color"] = ["#1f77b4"] * len(visits) if len(visits) > 0 else []

        source = ColumnDataSource(data=source_data)

        # Store visit data set
        visit_set = VisitDataSet(
            source=source,
            label=label,
            alpha=alpha,
            marker=marker,
            color_by_band=color_by_band,
            visible=True,
        )
        self._visit_sets[label] = visit_set

        # Create scatter config for this visit set
        y_column = "altitude" if "altitude" in visits.columns else "value"
        config = ScatterPlotConfig(
            name=label,
            y_column=y_column,
            offered_columns=tuple(visits.columns),
            figure_kwargs=scatter_kwargs,
        )
        self._elements.append(config)

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
        stripe_height = height if height is not None else 20
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

        # Create data source
        source = ColumnDataSource(data={"time": times, "value": values})

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

    def build(self) -> column:
        """Build and return the final Bokeh layout.

        Creates scatter plots, visit plots, and color stripes.

        Returns
        -------
        column
            Bokeh column layout containing all figures.
        """
        figures = []

        for element in self._elements:
            if isinstance(element, ScatterPlotConfig):
                if element.name in self._visit_sets:
                    # Visit plot
                    fig = self._create_visit_figure(element)
                else:
                    # Standard scatter plot
                    fig = self._create_scatter_figure(element)
            elif isinstance(element, ColorStripeConfig):
                # Color stripe
                fig = self._create_stripe_figure(element)
            else:
                # Fallback for unknown element types
                continue

            figures.append(fig)

        return column(*figures)

    def _create_scatter_figure(self, config: ScatterPlotConfig) -> figure:
        """Create a scatter plot figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the scatter plot.

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

        # Add scatter glyph with empty initial data
        scatter = Scatter(x="time", y=config.y_column, size=5)
        fig.add_glyph(ColumnDataSource(data={"time": [], config.y_column: []}), scatter)

        # Apply datetime tick formatter
        fig.xaxis[0].formatter = DatetimeTickFormatter(hours="%H:%M")

        return fig

    def _create_visit_figure(self, config: ScatterPlotConfig) -> figure:
        """Create a visit scatter plot figure.

        Parameters
        ----------
        config : ScatterPlotConfig
            Configuration for the visit plot.

        Returns
        -------
        figure
            Bokeh figure with visit scatter glyphs.
        """
        # Get visit data set
        visit_set = self._visit_sets[config.name]

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

        # Create scatter glyph with visit properties
        scatter = Scatter(
            x="time",
            y=config.y_column,
            size=5,
            marker=visit_set.marker,
            fill_color="color" if visit_set.color_by_band else "blue",
            line_color="color" if visit_set.color_by_band else "blue",
        )

        # Use the stored source from VisitDataSet
        fig.add_glyph(visit_set.source, scatter)

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
        # Get height from plot_heights, default to 20
        height = self._plot_heights.get(config.name, 20)

        # Create figure with no y-axis
        fig_kwargs = {
            "width": 1000,
            "x_axis_type": "datetime",
            "height": height,
            "y_axis_type": None,  # No y-axis
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
        # Each stripe is a horizontal band at y=0
        fig.rect(
            x="time",
            y=0,
            width=0.001,  # Small width in time units
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
    help="Path to visits file (parquet or CSV) to plot as visit markers.",
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
def main(
    date: str,
    scatter: tuple[str, ...],
    visits: tuple[str, ...],
    background: tuple[str, ...],
    output: str,
) -> None:
    """CLI entry point."""
    import pandas as pd

    from schedview.collect.visits import read_visits

    # Create DayObs from date
    dayobs = DayObs.from_date(date)

    # Build the timeline
    builder = TimelineBuilder(dayobs)

    # Add scatter plots
    for column_name in scatter:
        builder.add_scatter(y_column=column_name)

    # Add visits
    for visits_path in visits:
        # Load visits data
        visits_df = read_visits(dayobs, str(visits_path))

        # Use filename stem as label
        label = Path(visits_path).stem

        builder.add_visits(visits_df, label=label)

    # Add background stripes
    for bg_type in background:
        if bg_type == "sun_elevation":
            # Compute sun elevation throughout the day
            times = []
            elevations = []

            # Sample sun position every hour
            start_mjd = float(dayobs.start.mjd)
            end_mjd = float(dayobs.end.mjd)

            # Generate hourly samples
            current_mjd = start_mjd
            while current_mjd <= end_mjd:
                times.append(current_mjd)
                # Get sun position at this time
                from astropy.coordinates import get_body
                from astropy.time import Time

                sun = get_body("sun", Time(current_mjd, format="mjd"), location=dayobs.location)
                altaz = sun.altaz(location=dayobs.location)
                elevations.append(altaz.alt.deg)
                current_mjd += 1 / 24  # One hour

            sun_data = pd.Series(elevations, index=times)
            builder.add_color_stripe(sun_data, name="sun_elevation")

        elif bg_type == "moon_elevation":
            # Compute moon elevation throughout the day
            times = []
            elevations = []

            # Sample moon position every hour
            start_mjd = float(dayobs.start.mjd)
            end_mjd = float(dayobs.end.mjd)

            # Generate hourly samples
            current_mjd = start_mjd
            while current_mjd <= end_mjd:
                times.append(current_mjd)
                # Get moon position at this time
                from astropy.coordinates import get_body
                from astropy.time import Time

                moon = get_body("moon", Time(current_mjd, format="mjd"), location=dayobs.location)
                altaz = moon.altaz(location=dayobs.location)
                elevations.append(altaz.alt.deg)
                current_mjd += 1 / 24  # One hour

            moon_data = pd.Series(elevations, index=times)
            builder.add_color_stripe(moon_data, name="moon_elevation")

        else:
            # Unknown background type - could be extended in future
            pass

    # Build the layout
    layout = builder.build()

    # Write to HTML file
    output_path = Path(output)
    html = file_html(layout)
    output_path.write_text(html)


if __name__ == "__main__":
    main()
