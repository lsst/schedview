from typing import Any, Optional

import bokeh
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import bokeh.transform
import hvplot
import numpy as np
import pandas as pd
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.compute.astro
from schedview import band_column
from schedview.collect import read_opsim

from .colors import make_band_cmap

TIMELINE_TOOLTIPS = [
    (
        "Start time",
        "@start_timestamp{%F %T} UTC (mjd=@observationStartMJD{00000.00}, LST=@observationStartLST"
        + "\u00b0"
        + ")",
    ),
    ("flush by mjd", "@flush_by_mjd{00000.00}"),
    ("Scheduler note", "@scheduler_note"),
    ("Band", "@band"),
    (
        "Field coordinates",
        "RA=@fieldRA"
        + "\u00b0"
        + ", Decl=@fieldDec"
        + "\u00b0"
        + ", Az=@azimuth"
        + "\u00b0"
        + ", Alt=@altitude"
        + "\u00b0",
    ),
    ("Parallactic angle", "@paraAngle" + "\u00b0"),
    ("Rotator angle", "@rotTelPos" + "\u00b0"),
    ("Rotator angle (backup)", "@rotTelPos_backup" + "\u00b0"),
    ("Cumulative telescope azimuth", "@cummTelAz" + "\u00b0"),
    ("Airmass", "@airmass"),
    ("Moon distance", "@moonDistance" + "\u00b0"),
    (
        "Moon",
        "RA=@sunRA"
        + "\u00b0"
        + ", Decl=@sunDec"
        + "\u00b0"
        + ", Az=@sunAz"
        + "\u00b0"
        + ", Alt=@sunAlt"
        + "\u00b0"
        + ", phase=@moonPhase"
        + "\u00b0",
    ),
    (
        "Sun",
        "RA=@moonRA"
        + "\u00b0"
        + ", Decl=@moonDec"
        + "\u00b0"
        + ", Az=@moonAz"
        + "\u00b0"
        + ", Alt=@moonAlt"
        + "\u00b0"
        + ", elong=@solarElong"
        + "\u00b0",
    ),
    ("Sky brightness", "@skyBrightness mag arcsec^-2"),
    ("Exposure time", "@visitExposureTime seconds (@numExposures exposures)"),
    ("Visit time", "@visitTime seconds"),
    ("Slew distance", "@slewDistance" + "\u00b0"),
    ("Slew time", "@slewTime seconds"),
    ("Field ID", "@fieldId"),
    ("Proposal ID", "@proposalId"),
    ("Block ID", "@block_id"),
    ("Scripted ID", "@scripted_id"),
]

WEATHER_TOOLTIPS = [
    (
        "Seeing",
        '@seeingFwhm500" (500nm), @seeingFwhmEff" (Eff), @seeingFwhmGeom" (Geom)',
    ),
    ("Cloud", "@cloud"),
    ("5-sigma depth", "@fiveSigmaDepth"),
]


def visits_tooltips(weather: bool = False) -> list:
    tooltips = TIMELINE_TOOLTIPS

    if weather:
        tooltips += WEATHER_TOOLTIPS

    return tooltips


def plot_visits(visits):
    """Instantiate an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.read_opsim`

    Returns
    -------
    figure : `hvplot.ui.hvDataFrameExplorer`
        The figure itself.
    """
    visit_explorer = hvplot.explorer(
        visits, kind="scatter", x="start_timestamp", y="airmass", by=["scheduler_note"]
    )
    return visit_explorer


def create_visit_explorer(visits, night_date, observatory=None, timezone="Chile/Continental"):
    """Create an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `str` or `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.read_opsim`,
        or the name of a file from which such visits should be loaded.
    night_date : `datetime.date`
        The calendar date in the evening local time.
    observatory : `ModelObservatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None.
    timezone : `str`, optional
        _description_, by default "Chile/Continental"

    Returns
    -------
    figure : `hvplot.ui.hvDataFrameExplorer`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_visits`.
    """
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(night_date=night_date, site=site, timezone=timezone)
    start_time = Time(night_events.loc["sunset", "UTC"])
    end_time = Time(night_events.loc["sunrise", "UTC"])

    # Collect
    if isinstance(visits, str):
        visits = read_opsim(visits, Time(start_time).iso, Time(end_time).iso)

    # Plot
    data = {"visits": visits}
    visit_explorer = plot_visits(visits)

    return visit_explorer, data


def plot_visit_param_vs_time(
    visits: pd.DataFrame,
    column_name: str,
    plot: bokeh.plotting.figure | None = None,
    show_column_selector: bool = False,
    show_sim_selector: bool = False,
    hovertool: bool = True,
    color_transform: bokeh.models.mappers.CategoricalColorMapper | None = None,
    marker_transform: bokeh.models.mappers.CategoricalMarkerMapper | None = None,
    tooltips: str | None = None,
    **kwargs,
) -> bokeh.models.ui.ui_element.UIElement:
    """Plot a column in the visit table vs. time.

    Parameters
    ----------
    visits: `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`.
    column_name: `str`
        The name of the column to plot against time.
    plot: `bokeh.plotting.figure` or None
        The figure on which to plot the visits. None creates a new
        figure. Defaults to None.
    show_column_selector: `bool`
        Include a drop-down to select which column to plot?
        Defaults to False.
    color_transform: `CategoricalColorMapper` or None
        The color mapper from band to color.
    marker_transform: `CategoricalMarkerMapper` or None
        The marker mapper from label to marker.
    **kwargs
        Additional keyword arguments to be passed to
        `bokeh.plotting.figure.scatter`.

    Returns
    -------
    `plot` : `bokeh.models.plots.Plot`
        The figure with the plot.
    """
    if plot is None:
        plot = bokeh.plotting.figure(y_axis_label=column_name, x_axis_label="Time (UTC)")

    if len(visits) == 0:
        plot.text(x=0.5, y=0.5, text="No visits.")
        return plot

    # Make mypy happy
    assert isinstance(plot, bokeh.plotting.figure)

    if isinstance(visits, bokeh.models.ColumnarDataSource):
        source = visits
    else:
        source = bokeh.models.ColumnDataSource(visits)

    if "label" not in source.data:
        source.data["label"] = np.full_like(source.data["start_timestamp"], "")

    if "sim_alpha" not in source.data:
        source.data["sim_alpha"] = np.full_like(source.data["start_timestamp"], 1.0, dtype=np.float64)

    scatter_kwargs = {"fill_alpha": 0.0, "line_alpha": "sim_alpha", "name": "timeline"}

    if color_transform is None:
        scatter_kwargs["color"] = make_band_cmap(band_column(visits))
    else:
        scatter_kwargs["color"] = bokeh.transform.factor_cmap(
            band_column(visits), color_transform.palette, color_transform.factors
        )

    if marker_transform is not None:
        scatter_kwargs["marker"] = {"field": "label", "transform": marker_transform}

    scatter_kwargs.update(kwargs)

    timeline = plot.scatter(
        x="start_timestamp",
        y=column_name,
        source=source,
        **scatter_kwargs,
    )

    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    # Bokeh's fully automatic legend creation can't make legends for
    # color and marker independently. So, follow
    # https://discourse.bokeh.org/t/representing-data-with-two-categories-by-both-color-and-marker-shape/4122/4
    # Plot some fake points with colors, make them invisible,
    # and make a legend for them.
    # Then, do something analogous for makers (if needed).

    # Generate placement for sample points.
    # This needs to be in the plot to avoid messing up the axis limits,
    # but otherwise does not matter, because the points will be invisible.
    # Do not use data to get the sample y value, because the user can
    # change which data is getting plotted. Use a nan instead, which
    # will be ignored by the limit calculation.
    sample_x, sample_y = visits["start_timestamp"].iloc[0], np.nan

    # Create an invisible renderer to drive color legend:
    sample_color_renderer = plot.rect(
        x=sample_x,
        y=sample_y,
        height=1,
        width=1,
        fill_alpha=1,
        line_alpha=1,
        color=scatter_kwargs["color"].transform.palette,
    )
    sample_color_renderer.visible = False

    legend = bokeh.models.Legend(
        items=[
            bokeh.models.LegendItem(
                label=scatter_kwargs["color"].transform.factors[i], renderers=[sample_color_renderer], index=i
            )
            for i in range(len(scatter_kwargs["color"].transform.factors))
        ],
        location="bottom_center",
        orientation="horizontal",
    )
    plot.add_layout(legend, "below")

    if isinstance(marker_transform, bokeh.models.CategoricalMarkerMapper):
        # create an invisible renderer to drive shape legend
        sample_marker_renderer = plot.scatter(
            x=sample_x,
            y=sample_y,
            fill_alpha=0.0,
            line_alpha=1.0,
            color="black",
            marker=marker_transform.markers,
        )
        sample_marker_renderer.visible = False

        legend = bokeh.models.Legend(
            items=[
                bokeh.models.LegendItem(
                    label=marker_transform.factors[i], renderers=[sample_marker_renderer], index=i
                )
                for i in range(len(marker_transform.factors))
            ],
            location="bottom_left",
            orientation="vertical",
        )
        plot.add_layout(legend, "below")

    if hovertool:
        if tooltips is None:
            tooltips = visits_tooltips()

        hover_tool = bokeh.models.HoverTool(
            renderers=[timeline], tooltips=tooltips, formatters={"@start_timestamp": "datetime"}
        )
        plot.add_tools(hover_tool)

    if show_column_selector:
        ignored_columns = {"level_0", "index", "sim_alpha", "sim_index"}
        # Only offer numeric fields as options
        options = []
        # Use a loop instead of a list comprehension to make it easier
        # to appease mypy
        for k in sorted(set(source.column_names) - ignored_columns):
            column_data = source.data[k]
            assert isinstance(column_data, np.ndarray)
            if np.issubdtype(column_data.dtype, np.number):
                options.append(k)

        column_selector = bokeh.models.Select(value=column_name, options=options, name="visitcolselect")

        column_selector_callback = bokeh.models.CustomJS(
            args={"timeline": timeline, "source": source, "yaxis": plot.yaxis[0]},
            code="""
                timeline.glyph.y.field = this.value
                yaxis.axis_label = this.value
                source.change.emit()
            """,
        )
        column_selector.js_on_change("value", column_selector_callback)

    if show_sim_selector:
        if "label" not in source.column_names:
            raise ValueError("A sim selector needs the label column")
        options = ["All"] + list(o for o in np.unique(source.data["label"]) if o != "Completed")
        default_sim = "All"
        sim_selector = bokeh.models.Select(value=default_sim, options=options, name="simselect")

        sim_selector_callback = bokeh.models.CustomJS(
            args={"source": source},
            code="""
                for (let i = 0; i < source.data['label'].length; i++) {
                    if (source.data['label'][i] === 'Completed') {
                        source.data['sim_alpha'][i] = 1.0;
                    } else if (['All', source.data['label'][i]].includes(this.value)) {
                        source.data['sim_alpha'][i] = 0.8;
                    } else {
                        source.data['sim_alpha'][i] = 0.0;
                    }
                }
                source.change.emit()
            """,
        )
        sim_selector.js_on_change("value", sim_selector_callback)

    if show_column_selector or show_sim_selector:
        selector_row_contents = []
        if show_column_selector:
            selector_row_contents.append(column_selector)
        if show_sim_selector:
            selector_row_contents.append(sim_selector)
        ui_element = bokeh.layouts.column([bokeh.layouts.row(selector_row_contents), plot])
    else:
        ui_element = plot

    return ui_element


def create_visit_table(
    visits: pd.DataFrame | bokeh.models.ColumnarDataSource,
    visible_column_names: list[str] = [
        "observationId",
        "observationStartMJD",
        "fieldRA",
        "fieldDec",
        "band",
    ],
    show: bool = True,
    **data_table_kwargs: Optional[Any],
) -> bokeh.models.ui.ui_element.UIElement:
    """Create an interactive table of visits.

    Parameters
    ----------
    visits : `pd.DataFrame` or `bokeh.models.ColumnarDataSource`
        The visits to include in the table
    visible_column_names : `list[str]`
        The columns to display, by default
        ['observationId', 'observationStartMJD',
        'fieldRA', 'fieldDec', 'band']
    show : `bool`
        Show the plot?, by default True

    Returns
    -------
    element : `bokeh.models.ui.ui_element.UIElement`
        The bokeh UI element with the table.
    """

    data = (
        visits
        if isinstance(visits, bokeh.models.ColumnarDataSource)
        else bokeh.models.ColumnDataSource(visits)
    )

    date_columns = []
    date_colname = (
        "start_timestamp" if "start_timestamp" in data.column_names else "observationStartDatetime64"
    )
    if date_colname in data.column_names:
        date_columns = [
            bokeh.models.TableColumn(
                field="start_timestamp",
                title="UTC Time",
                formatter=bokeh.models.DateFormatter(format="%H:%M:%S"),
            )
        ]
        visible_column_names.insert(0, date_colname)

    data_columns = [
        bokeh.models.TableColumn(field=cn, title=cn, name=f"tablecol{cn}", visible=cn in visible_column_names)
        for cn in data.column_names
        if cn != date_colname
    ]
    columns = date_columns + data_columns
    visit_table = bokeh.models.DataTable(
        source=data, columns=columns, name="visit_table", **data_table_kwargs
    )
    multi_choice = bokeh.models.MultiChoice(value=visible_column_names, options=data.column_names, height=128)

    table_update_callback = bokeh.models.CustomJS(
        args={"multi_choice": multi_choice, "visit_table": visit_table},
        code="""
            for (var col_idx=0; col_idx<visit_table.columns.length; col_idx++) {
                visit_table.columns[col_idx].visible = false
                for (var choice_idx=0; choice_idx<multi_choice.value.length; choice_idx++) {
                    if (visit_table.columns[col_idx].field == multi_choice.value[choice_idx]) {
                        visit_table.columns[col_idx].visible = true
                    }
                }
            }
            visit_table.change.emit()
        """,
    )

    multi_choice.js_on_change("value", table_update_callback)

    ui_element = bokeh.layouts.column([multi_choice, visit_table])

    if show:
        bokeh.io.show(ui_element)

    return ui_element
