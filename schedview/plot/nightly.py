"""Plots that summarize a night's visits and other parameters."""

import bokeh
import bokeh.models
import colorcet
import numpy as np

from schedview import band_column

from .colors import PLOT_BAND_COLORS
from .visits import visits_tooltips

DEFAULT_EVENT_LABELS = {
    "sunset": "sunset",
    "sun_n12_setting": "sun alt=-12" + "\u00b0",
    "sun_n18_setting": "sun alt=-18" + "\u00b0",
    "sun_n18_rising": "sun alt=-18" + "\u00b0",
    "sun_n12_rising": "sun alt=-12" + "\u00b0",
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

BAND_SHAPES = {
    "y": "circle",
    "z": "hex",
    "i": "star",
    "r": "square",
    "g": "diamond",
    "u": "triangle",
}


def _add_almanac_events(fig, almanac_events, event_labels, event_colors):
    for event, row in almanac_events.iterrows():
        if event_labels[event] is None:
            continue

        event_marker = bokeh.models.Span(location=row.UTC, dimension="height", line_color=event_colors[event])
        fig.add_layout(event_marker)
        event_label = bokeh.models.Label(
            x=row.UTC,
            y=fig.y_range.start,
            text=" " + event_labels[event],
            angle=90,
            angle_units="deg",
            text_color=event_colors[event],
        )
        fig.add_layout(event_label)


def plot_airmass_vs_time(
    visits,
    almanac_events,
    band_colors=PLOT_BAND_COLORS,
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
        Mapping of almanac events to labels.
        Default is `DEFAULT_EVENT_LABELS`.
    event_colors : `dict`
        Mapping of almanac events to colors.
        Default is `DEFAULT_EVENT_COLORS`.
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
        visits = visits_ds.to_df()
    else:
        visits_ds = bokeh.models.ColumnDataSource(visits)

    filter_color_mapper = bokeh.models.CategoricalColorMapper(
        factors=tuple(band_colors.keys()),
        palette=tuple(band_colors.values()),
        name=band_column(visits),
    )
    fig.line("start_timestamp", "airmass", source=visits_ds, color="gray")
    fig.circle(
        "start_timestamp",
        "airmass",
        radius=0.2,
        source=visits_ds,
        color={"field": band_column(visits), "transform": filter_color_mapper},
        legend_field=band_column(visits),
        name="visit_airmass",
    )

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_airmass"})
    hover_tool.tooltips = visits_tooltips()
    hover_tool.formatters = {"@start_timestamp": "datetime"}
    fig.add_tools(hover_tool)

    plot_airmass_limit = np.round(np.max(visits.airmass), 1) + 0.1
    fig.y_range = bokeh.models.Range1d(plot_airmass_limit, 1)
    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
    moved_legend = fig.legend[0].clone()
    fig.legend[0].destroy()
    fig.add_layout(moved_legend, "left")

    if almanac_events is not None:
        _add_almanac_events(fig, almanac_events, event_labels, event_colors)

    return fig


def make_airmass_tick_formatter():
    """Make a bokeh.models.TickFormatter for airmass values"""
    js_code = """
        const cos_zd = Math.sin(tick * Math.PI / 180.0)
        const a = 462.46 + 2.8121/(cos_zd**2 + 0.22*cos_zd + 0.01)
        const airmass = Math.sqrt((a*cos_zd)**2 + 2*a + 1) - a * cos_zd
        return airmass.toFixed(2)
    """

    return bokeh.models.CustomJSTickFormatter(code=js_code)


def plot_alt_vs_time(
    visits,
    almanac_events,
    band_shapes=BAND_SHAPES,
    event_labels=DEFAULT_EVENT_LABELS,
    event_colors=DEFAULT_EVENT_COLORS,
    figure=None,
    note_column=None,
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
        Mapping of almanac events to labels.
        Default is `DEFAULT_EVENT_LABELS`.
    event_colors : `dict`
        Mapping of almanac events to colors.
        Default is `DEFAULT_EVENT_COLORS`.
    figure : `bokeh.plotting.Figure`
        Bokeh figure object to plot on.  If None, a new figure will be created.
    note_column : `str` or None
        The column to use as the note to map to color.
        Defaults to None, which defaults `scheduler_note` if it is present
        in the visit datasource, otherwise `note`.

    Returns
    -------
    fig : `bokeh.plotting.Figure`
        Bokeh figure object
    """

    if note_column is None:
        if isinstance(visits, bokeh.models.ColumnDataSource):
            scheduler_note_present = "scheduler_note" in visits.data
        else:
            scheduler_note_present = "scheduler_note" in visits
        note_column = "scheduler_note" if scheduler_note_present else "note"

    for time_column in "start_timestamp", "observationStartDatetime64":
        if isinstance(visits, bokeh.models.ColumnDataSource):
            if time_column in visits.data:
                break
        else:
            if time_column in visits:
                break

    if figure is None:
        fig = bokeh.plotting.figure(
            title="Altitude",
            x_axis_label="Time (UTC)",
            y_axis_label="Altitude",
            frame_width=512,
            frame_height=512,
        )
    else:
        fig = figure

    if isinstance(visits, bokeh.models.ColumnDataSource):
        visits_ds = visits
    else:
        visits_ds = bokeh.models.ColumnDataSource(visits)

    note_values = np.unique(visits_ds.data[note_column])
    too_many_note_values = len(note_values) > len(colorcet.palette["glasbey"])

    if not too_many_note_values:
        note_color_mapper = bokeh.models.CategoricalColorMapper(
            factors=note_values, palette=colorcet.palette["glasbey"][: len(note_values)], name=note_column
        )

        if "note_and_filter" not in visits_ds.column_names:
            note_and_filter = tuple(
                [
                    f"{n} in {f}"
                    for n, f in zip(visits_ds.data[note_column], visits_ds.data[band_column(visits)])
                ]
            )
            visits_ds.add(note_and_filter, "note_and_filter")

    filter_marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=tuple(band_shapes.keys()),
        markers=tuple(band_shapes.values()),
        name=band_column(visits),
    )

    fig.line(time_column, "altitude", source=visits_ds, color="gray")
    if too_many_note_values:
        fig.scatter(
            time_column,
            "altitude",
            source=visits_ds,
            marker={"field": band_column(visits), "transform": filter_marker_mapper},
            size=5,
            legend_field=band_column(visits),
            name="visit_altitude",
        )
    else:
        fig.scatter(
            time_column,
            "altitude",
            source=visits_ds,
            color={"field": note_column, "transform": note_color_mapper},
            marker={"field": band_column(visits), "transform": filter_marker_mapper},
            size=5,
            legend_field="note_and_filter",
            name="visit_altitude",
        )

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_altitude"})
    hover_tool.tooltips = visits_tooltips()
    hover_tool.formatters = {"@start_timestamp": "datetime"}
    fig.add_tools(hover_tool)

    fig.y_range = bokeh.models.Range1d(0, 90)
    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    moved_legend = fig.legend[0].clone()
    fig.legend[0].destroy()
    fig.add_layout(moved_legend, "left")

    fig.yaxis[0].ticker.desired_num_ticks = 10

    fig.extra_y_ranges = {"airmass": fig.y_range}
    fig.add_layout(bokeh.models.LinearAxis(), "right")
    fig.yaxis[1].ticker.desired_num_ticks = fig.yaxis[0].ticker.desired_num_ticks
    fig.yaxis[1].formatter = make_airmass_tick_formatter()
    fig.yaxis[1].minor_tick_line_alpha = 0
    fig.yaxis[1].axis_label = "Airmass"

    if almanac_events is not None:
        _add_almanac_events(fig, almanac_events, event_labels, event_colors)

    return fig


def _add_alt_graticules(fig, transform, min_alt=0, max_alt=90, alt_step=30, label=True):
    """Add altitude graticules to a figure"""
    for alt in np.arange(min_alt, max_alt + alt_step, alt_step):
        azimuth = np.arange(0, 361, 1)
        zd = 90 - np.full_like(azimuth, alt)
        graticule_source = bokeh.models.ColumnDataSource({"azimuth": azimuth, "zd": zd})

        fig.line(
            transform.y,
            transform.x,
            source=graticule_source,
            color="gray",
            line_width=1,
            line_alpha=0.5,
        )

        if label and alt < 90:
            label_source = bokeh.models.ColumnDataSource(
                {"azimuth": [0], "zd": [90 - alt], "label": [f" {alt}\u00b0"]}
            )
            fig.text(
                transform.y,
                transform.x,
                source=label_source,
                text="label",
                text_color="gray",
                text_font_size={"value": "10px"},
                text_align="left",
                text_baseline="top",
            )


def _add_az_graticules(fig, transform, min_alt=0, min_az=0, max_az=360, az_step=30, label=True):
    """Add azimuth graticules to a figure"""
    for azimuth in np.arange(min_az, max_az + az_step, az_step):
        zd = [0, 90 - min_alt]
        azimuths = [azimuth, azimuth]
        graticule_source = bokeh.models.ColumnDataSource({"azimuth": azimuths, "zd": zd})

        fig.line(
            transform.y,
            transform.x,
            source=graticule_source,
            color="gray",
            line_width=1,
            line_alpha=0.5,
        )

        if label:
            if azimuth % 360 == 0:
                graticule_label = "N"
                text_align = "center"
                text_baseline = "bottom"
            elif azimuth % 360 == 90:
                graticule_label = "E "
                text_align = "right"
                text_baseline = "middle"
            elif azimuth % 360 == 180:
                graticule_label = "S"
                text_align = "center"
                text_baseline = "top"
            elif azimuth % 360 == 270:
                graticule_label = " W"
                text_align = "left"
                text_baseline = "middle"
            else:
                graticule_label = f"{azimuth}\u00b0"
                text_align = "right" if azimuth < 180 else "left"
                text_baseline = "bottom" if azimuth < 90 or azimuth > 270 else "top"

            label_source = bokeh.models.ColumnDataSource(
                {"azimuth": [azimuth], "zd": [90 - min_alt], "label": [graticule_label]}
            )
            fig.text(
                transform.y,
                transform.x,
                source=label_source,
                text="label",
                text_color="gray",
                text_font_size={"value": "10px"},
                text_align=text_align,
                text_baseline=text_baseline,
            )


def plot_polar_alt_az(visits, band_shapes=BAND_SHAPES, figure=None, legend=True, note_column=None):
    """Plot airmass vs. time for a set of visits

    Parameters
    ----------
    visits : `pandas.DataFrame` or `bokeh.models.ColumnDataSource`
        Dataframe or ColumnDataSource containing visit information.
    almanac_events : `pandas.DataFrame`
        Dataframe containing almanac events.
    band_colors : `dict`
        Mapping of filter names to colors.  Default is `BAND_COLORS`.
    figure : `bokeh.plotting.Figure`
        Bokeh figure object to plot on.  If None, a new figure will be created.
    legend : `bool`
        Generate a legend. Default is True.

    Returns
    -------
    fig : `bokeh.plotting.Figure`
        Bokeh figure object
    """
    if note_column is None:
        if isinstance(visits, bokeh.models.ColumnDataSource):
            scheduler_note_present = "scheduler_note" in visits.data
        else:
            scheduler_note_present = "scheduler_note" in visits
        note_column = "scheduler_note" if scheduler_note_present else "note"

    if figure is None:
        fig = bokeh.plotting.figure(
            title="Horizon Coordinates",
            x_axis_type=None,
            y_axis_type=None,
            frame_width=512,
            frame_height=512,
        )
    else:
        fig = figure

    if isinstance(visits, bokeh.models.ColumnDataSource):
        visits_ds = visits
    else:
        visits_ds = bokeh.models.ColumnDataSource(visits)

    if "HA" not in visits_ds.column_names:
        hour_angle = (
            (np.array(visits_ds.data["observationStartLST"]) - np.array(visits_ds.data["fieldRA"]))
            * 24.0
            / 360.0
        )
        hour_angle = np.mod(hour_angle + 12.0, 24) - 12
        visits_ds.add(hour_angle, "HA")

    if "zd" not in visits_ds.column_names:
        visits_ds.add(90 - np.array(visits_ds.data["altitude"]), "zd")

    note_values = np.unique(visits_ds.data[note_column])
    too_many_note_values = len(note_values) > len(colorcet.palette["glasbey"])

    if not too_many_note_values:
        note_color_mapper = bokeh.models.CategoricalColorMapper(
            factors=note_values, palette=colorcet.palette["glasbey"][: len(note_values)], name=note_column
        )

        if "note_and_filter" not in visits_ds.column_names:
            note_and_filter = tuple(
                [
                    f"{n} in {f}"
                    for n, f in zip(visits_ds.data[note_column], visits_ds.data[band_column(visits)])
                ]
            )
            visits_ds.add(note_and_filter, "note_and_filter")

    filter_marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=tuple(band_shapes.keys()),
        markers=tuple(band_shapes.values()),
        name=band_column(visits),
    )

    polar_transform = bokeh.models.PolarTransform(
        angle="azimuth", radius="zd", angle_units="deg", direction="clock"
    )

    fig.line(polar_transform.y, polar_transform.x, source=visits_ds, color="gray")
    if too_many_note_values:
        fig.scatter(
            polar_transform.y,
            polar_transform.x,
            source=visits_ds,
            marker={"field": band_column(visits), "transform": filter_marker_mapper},
            size=5,
            legend_field=band_column(visits),
            name="visit_altitude",
        )
    else:
        fig.scatter(
            polar_transform.y,
            polar_transform.x,
            source=visits_ds,
            color={"field": note_column, "transform": note_color_mapper},
            marker={"field": band_column(visits), "transform": filter_marker_mapper},
            size=5,
            legend_field="note_and_filter",
            name="visit_altitude",
        )

    _add_alt_graticules(fig, polar_transform)
    _add_az_graticules(fig, polar_transform)

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_altitude"})
    hover_tool.tooltips = visits_tooltips()
    hover_tool.formatters = {"@start_timestamp": "datetime"}
    fig.add_tools(hover_tool)

    if legend:
        moved_legend = fig.legend[0].clone()
        fig.legend[0].destroy()
        fig.add_layout(moved_legend, "left")
    else:
        fig.legend.visible = False

    return fig
