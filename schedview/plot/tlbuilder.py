"""Timeline Builder - Phase A implementation.

Core builder infrastructure, scatter plot support,
shared datetime x-axis, and minimal CLI.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Self

import numpy as np
from astropy.time import Time
from bokeh.embed import file_html
from bokeh.layouts import column
from bokeh.models import ColumnDataSource, Range1d, Scatter, DatetimeTickFormatter
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


class ColorStripeConfig:
    """Stub class for color stripe configuration.

    Not implemented in Phase A.
    """

    pass


class VisitDataSet:
    """Stub class for visit data set.

    Not implemented in Phase A.
    """

    pass


class TimelineBuilder:
    """Build interactive timeline visualizations.

    Phase A provides:
    - Core builder infrastructure
    - Scatter plot support
    - Shared datetime x-axis
    - Correct MJD to datetime64 conversion
    - Vertical stacking of scatter figures
    - Minimal CLI v1

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

    def build(self) -> column:
        """Build and return the final Bokeh layout.

        Creates scatter plots only (Phase A).

        Returns
        -------
        column
            Bokeh column layout containing all figures.
        """
        figures = []

        for element in self._elements:
            if isinstance(element, ScatterPlotConfig):
                fig = self._create_scatter_figure(element)
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
        # Start with defaults, then update with builder kwargs, then config kwargs
        fig_kwargs = {"width": 1000, "x_axis_type": "datetime"}
        if self._figure_kwargs:
            fig_kwargs.update(self._figure_kwargs)
        if config.figure_kwargs:
            fig_kwargs.update(config.figure_kwargs)
        fig_kwargs["height"] = height
        fig_kwargs["x_range"] = self._shared_x_range

        fig = figure(**fig_kwargs)

        # Add scatter glyph
        scatter = Scatter(x="time", y=config.y_column, size=5)
        fig.add_glyph(ColumnDataSource(data={"time": []}), scatter)

        # Apply datetime tick formatter
        fig.xaxis[0].formatter = DatetimeTickFormatter(hours="%H:%M")

        return fig


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns
    -------
    ArgumentParser
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Build timeline visualizations for Rubin Observatory observing nights."
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Date of the observing night (YYYY-MM-DD format).",
    )
    parser.add_argument(
        "--scatter",
        action="append",
        default=[],
        help="Column name to plot as a scatter plot (can be specified multiple times).",
    )
    parser.add_argument(
        "--output",
        default="timeline.html",
        help="Output HTML file path (default: timeline.html).",
    )
    return parser


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


def main() -> None:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Create DayObs from date
    dayobs = DayObs.from_date(args.date)

    # Build the timeline
    layout = build_timeline(dayobs, args.scatter)

    # Write to HTML file
    output_path = Path(args.output)
    html = file_html(layout)
    output_path.write_text(html)


if __name__ == "__main__":
    main()
