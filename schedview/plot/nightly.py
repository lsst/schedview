"""Plots that summarize a night's visits and other parameters."""

import bokeh
import colorcet
import numpy as np

from .visitmap import BAND_COLORS

DEFAULT_EVENT_LABELS = {
    "sunset": "sunset",
    "sun_n12_setting": "sun alt=-12" + "\u00B0",
    "sun_n18_setting": "sun alt=-18" + "\u00B0",
    "sun_n18_rising": "sun alt=-18" + "\u00B0",
    "sun_n12_rising": "sun alt=-12" + "\u00B0",
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


def _visits_tooltips(visits, weather=False):
    deg = "\u00b0"
    tooltips = [
        (
            "Start time",
            "@start_date{%F %T} UTC (mjd=@observationStartMJD{00000.00}, LST=@observationStartLST"
            + deg
            + ")",
        ),
        ("flush by mjd", "@flush_by_mjd{00000.00}"),
        ("Note", "@note"),
        ("Filter", "@filter"),
        (
            "Field coordinates",
            "RA=@fieldRA" + deg + ", Decl=@fieldDec" + deg + ", Az=@azimuth" + deg + ", Alt=@altitude" + deg,
        ),
        ("Parallactic angle", "@paraAngle" + deg),
        ("Rotator angle", "@rotTelPos" + deg),
        ("Rotator angle (backup)", "@rotTelPos_backup" + deg),
        ("Cumulative telescope azimuth", "@cummTelAz" + deg),
        ("Airmass", "@airmass"),
        ("Moon distance", "@moonDistance" + deg),
        (
            "Moon",
            "RA=@sunRA"
            + deg
            + ", Decl=@sunDec"
            + deg
            + ", Az=@sunAz"
            + deg
            + ", Alt=@sunAlt"
            + deg
            + ", phase=@moonPhase"
            + deg,
        ),
        (
            "Sun",
            "RA=@moonRA"
            + deg
            + ", Decl=@moonDec"
            + deg
            + ", Az=@moonAz"
            + deg
            + ", Alt=@moonAlt"
            + deg
            + ", elong=@solarElong"
            + deg,
        ),
        ("Sky brightness", "@skyBrightness mag arcsec^-2"),
        ("Exposure time", "@visitExposureTime seconds (@numExposures exposures)"),
        ("Visit time", "@visitTime seconds"),
        ("Slew distance", "@slewDistance" + deg),
        ("Slew time", "@slewTime seconds"),
        ("Field ID", "@fieldId"),
        ("Proposal ID", "@proposalId"),
        ("Block ID", "@block_id"),
        ("Scripted ID", "@scripted_id"),
    ]

    if weather:
        tooltips += [
            (
                "Seeing",
                '@seeingFwhm500" (500nm), @seeingFwhmEff" (Eff), @seeingFwhmGeom" (Geom)',
            ),
            ("Cloud", "@cloud"),
            ("5-sigma depth", "@fiveSigmaDepth"),
        ]

    return tooltips


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
        name="filter",
    )
    fig.line("start_date", "airmass", source=visits_ds, color="gray")
    fig.circle(
        "start_date",
        "airmass",
        source=visits_ds,
        color={"field": "filter", "transform": filter_color_mapper},
        legend_field="filter",
        name="visit_airmass",
    )

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_airmass"})
    hover_tool.tooltips = _visits_tooltips(visits)
    hover_tool.formatters = {"@start_date": "datetime"}
    fig.add_tools(hover_tool)

    plot_airmass_limit = np.round(np.max(visits.airmass), 1) + 0.1
    fig.y_range = bokeh.models.Range1d(plot_airmass_limit, 1)
    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
    fig.add_layout(fig.legend[0], "left")

    if almanac_events is not None:
        _add_almanac_events(fig, almanac_events, event_labels, event_colors)

    return fig


def _make_airmass_tick_formatter():
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

    ha_color_mapper = bokeh.models.LinearColorMapper(low=-5, high=5, palette=colorcet.palette["bkr"])

    filter_marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=tuple(band_shapes.keys()),
        markers=tuple(band_shapes.values()),
        name="filter",
    )

    fig.line("start_date", "altitude", source=visits_ds, color="gray")
    fig.scatter(
        "start_date",
        "altitude",
        source=visits_ds,
        color={"field": "HA_hours", "transform": ha_color_mapper},
        marker={"field": "filter", "transform": filter_marker_mapper},
        size=5,
        legend_field="filter",
        name="visit_altitude",
    )

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_altitude"})
    hover_tool.tooltips = _visits_tooltips(visits)
    hover_tool.formatters = {"@start_date": "datetime"}
    fig.add_tools(hover_tool)

    fig.y_range = bokeh.models.Range1d(0, 90)
    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    color_bar = bokeh.models.ColorBar(
        color_mapper=ha_color_mapper, width=8, location=(0, 0), title="H.A. (hours)"
    )
    fig.add_layout(color_bar, "left")
    fig.add_layout(fig.legend[0], "left")

    fig.yaxis[0].ticker.desired_num_ticks = 10

    fig.extra_y_ranges = {"airmass": fig.y_range}
    fig.add_layout(bokeh.models.LinearAxis(), "right")
    fig.yaxis[1].ticker.desired_num_ticks = fig.yaxis[0].ticker.desired_num_ticks
    fig.yaxis[1].formatter = _make_airmass_tick_formatter()
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


def plot_polar_alt_az(visits, band_shapes=BAND_SHAPES, figure=None, legend=True):
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

    if "HA_hours" not in visits_ds.column_names:
        hour_angle = (
            (np.array(visits_ds.data["observationStartLST"]) - np.array(visits_ds.data["fieldRA"]))
            * 24.0
            / 360.0
        )
        hour_angle = np.mod(hour_angle + 12.0, 24) - 12
        visits_ds.add(hour_angle, "HA_hours")

    if "zd" not in visits_ds.column_names:
        visits_ds.add(90 - np.array(visits_ds.data["altitude"]), "zd")

    ha_color_mapper = bokeh.models.LinearColorMapper(low=-5, high=5, palette=colorcet.palette["bkr"])

    filter_marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=tuple(band_shapes.keys()),
        markers=tuple(band_shapes.values()),
        name="filter",
    )

    polar_transform = bokeh.models.PolarTransform(
        angle="azimuth", radius="zd", angle_units="deg", direction="clock"
    )

    fig.line(polar_transform.y, polar_transform.x, source=visits_ds, color="gray")
    fig.scatter(
        polar_transform.y,
        polar_transform.x,
        source=visits_ds,
        color={"field": "HA_hours", "transform": ha_color_mapper},
        marker={"field": "filter", "transform": filter_marker_mapper},
        size=5,
        legend_field="filter",
        name="visit_altitude",
    )

    _add_alt_graticules(fig, polar_transform)
    _add_az_graticules(fig, polar_transform)

    hover_tool = bokeh.models.HoverTool()
    hover_tool.renderers = fig.select({"name": "visit_altitude"})
    hover_tool.tooltips = _visits_tooltips(visits)
    hover_tool.formatters = {"@start_date": "datetime"}
    fig.add_tools(hover_tool)

    color_bar = bokeh.models.ColorBar(
        color_mapper=ha_color_mapper, width=8, location=(0, 0), title="H.A. (hours)"
    )
    if legend:
        fig.add_layout(color_bar, "left")
        fig.add_layout(fig.legend[0], "left")
    else:
        fig.legend.visible = False

    return fig
