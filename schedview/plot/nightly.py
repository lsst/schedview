"""Plots that summarize a night's visits and other parameters."""

import bokeh
import numpy as np
from .visitmap import BAND_COLORS

DEFAULT_EVENT_LABELS = {
    "sunset": "sunset",
    "sun_n12_setting": "sun alt=12" + "\u00B0",
    "sun_n18_setting": "sun alt=18" + "\u00B0",
    "sun_n18_rising": "sun alt=18" + "\u00B0",
    "sun_n12_rising": "sun alt=12" + "\u00B0",
    "sunrise": "sunrise",
    "moonrise": "moonrise",
    "moonset": "moonset",
    "night_middle": None,
}

DEFAULT_EVENT_COLORS = {
    "sunset": "darkblue",
    "sun_n12_setting": "blue",
    "sun_n18_setting": "lightblue",
    "sun_n18_rising": "lightblue",
    "sun_n12_rising": "blue",
    "sunrise": "darkblue",
    "moonrise": "green",
    "moonset": "green",
    "night_middle": None,
}


def plot_airmass_vs_time(
    visits,
    almanac_events,
    band_colors=BAND_COLORS,
    event_labels=DEFAULT_EVENT_LABELS,
    event_colors=DEFAULT_EVENT_COLORS,
    figure=None,
):
    """Plot airmass vs. time for a set of visits

    Parameters
    ----------
    visits : `pandas.DataFrame` or `bokeh.models.ColumnDataSource`
        Dataframe or ColumnDataSource containing visit information.
    almanac_events : `pandas.DataFrame`
        Dataframe containing almanac events.
    band_colors : `dict`
        Mapping of filter names to colors.  Default is `BAND_COLORS`.
    event_labels : `dict`
        Mapping of almanac events to labels.  Default is `DEFAULT_EVENT_LABELS`.
    event_colors : `dict`
        Mapping of almanac events to colors.  Default is `DEFAULT_EVENT_COLORS`.
    figure : `bokeh.plotting.Figure`
        Bokeh figure object to plot on.  If None, a new figure will be created.

    Returns
    -------
    fig : `bokeh.plotting.Figure`
        Bokeh figure object
    """

    if figure is None:
        fig = bokeh.plotting.figure(
            title="Airmass",
            x_axis_label="Time (UTC)",
            y_axis_label="Airmass",
            frame_width=768,
            frame_height=512,
        )
    else:
        fig = figure

    if isinstance(visits, bokeh.models.ColumnDataSource):
        visits_ds = visits
    else:
        visits_ds = bokeh.models.ColumnDataSource(visits)

    filter_color_mapper = bokeh.models.CategoricalColorMapper(
        factors=tuple(band_colors.keys()),
        palette=tuple(band_colors.values()),
        name="filter",
    )
    fig.line("start_date", "airmass", source=visits_ds, color="gray")
    fig.circle(
        "start_date",
        "airmass",
        source=visits_ds,
        color={"field": "filter", "transform": filter_color_mapper},
        legend_field="filter",
    )
    plot_airmass_limit = np.round(np.max(visits.airmass), 1) + 0.1
    fig.y_range = bokeh.models.Range1d(plot_airmass_limit, 1)
    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
    fig.add_layout(fig.legend[0], "left")

    if almanac_events is not None:
        for event, row in almanac_events.iterrows():
            if event_labels[event] is None:
                continue

            event_marker = bokeh.models.Span(
                location=row.UTC, dimension="height", line_color=event_colors[event]
            )
            fig.add_layout(event_marker)
            event_label = bokeh.models.Label(
                x=row.UTC,
                y=plot_airmass_limit,
                text=" " + event_labels[event],
                angle=90,
                angle_units="deg",
                text_color=event_colors[event],
            )
            fig.add_layout(event_label)

    return fig
