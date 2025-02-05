from typing import Any, Optional

import bokeh
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import hvplot
import numpy as np
import pandas as pd
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.compute.astro
from schedview.collect import read_opsim

from .colors import make_band_cmap


def visits_tooltips(weather: bool = False) -> list:
    deg = "\u00b0"
    tooltips = [
        (
            "Start time",
            "@start_date{%F %T} UTC (mjd=@observationStartMJD{00000.00}, LST=@observationStartLST"
            + deg
            + ")",
        ),
        ("flush by mjd", "@flush_by_mjd{00000.00}"),
        ("Scheduler note", "@scheduler_note"),
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
        visits, kind="scatter", x="start_date", y="airmass", by=["scheduler_note"]
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
    hovertool: bool = True,
    **kwargs,
) -> bokeh.models.ui.ui_element.UIElement:
    """Plot a column in the visit table vs. time.

    Parameters
    ----------
    `visits`: `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`.
    `column_name`: `str`
        The name of the column to plot against time.
    `plot`: `bokeh.plotting.figure` or None
        The figure on which to plot the visits. None creates a new
        figure. Defaults to None.
    `show_column_selector`: `bool`
        Include a drop-down to select which column to plot?
        Defaults to False.

    Returns
    -------
    `plot` : `bokeh.models.plots.Plot`
        The figure with the plot.
    """
    if plot is None:
        plot = bokeh.plotting.figure(y_axis_label=column_name, x_axis_label="Time (UTC)")

    # Make mypy happy
    assert isinstance(plot, bokeh.plotting.figure)

    data = (
        visits
        if isinstance(visits, bokeh.models.ColumnarDataSource)
        else bokeh.models.ColumnDataSource(visits)
    )

    circle_kwargs = {"fill_alpha": 0.3, "marker": "circle"}
    circle_kwargs.update(kwargs)

    band_column = "band" if "band" in visits else "filter"
    band_cmap = make_band_cmap(band_column)

    timeline = plot.scatter(
        x="start_date",
        y=column_name,
        color=band_cmap,
        source=data,
        legend_group="filter",
        **circle_kwargs,
    )

    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    legend = plot.legend[0]
    legend.orientation = "horizontal"
    plot.add_layout(legend, "below")

    if hovertool:
        hover_tool = bokeh.models.HoverTool(
            renderers=[timeline], tooltips=visits_tooltips(), formatters={"@start_date": "datetime"}
        )
        plot.add_tools(hover_tool)

    if show_column_selector:
        # Only offer numeric fields as options
        options = []
        # Use a loop instead of a list comprehension to make it easier
        # to appease mypy
        for k in data.column_names:
            column_data = data.data[k]
            assert isinstance(column_data, np.ndarray)
            if np.issubdtype(column_data.dtype, np.number):
                options.append(k)

        column_selector = bokeh.models.Select(value=column_name, options=options, name="visitcolselect")

        timeline_callback = bokeh.models.CustomJS(
            args={"timeline": timeline, "data": data, "yaxis": plot.yaxis[0]},
            code="""
                timeline.glyph.y.field = this.value
                yaxis.axis_label = this.value
                data.change.emit()
            """,
        )
        column_selector.js_on_change("value", timeline_callback)
        ui_element = bokeh.layouts.column([column_selector, plot])
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
        "filter",
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
        'fieldRA', 'fieldDec', 'filter']
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
    date_colname = "start_date" if "start_date" in data.column_names else "observationStartDatetime64"
    if date_colname in data.column_names:
        date_columns = [
            bokeh.models.TableColumn(
                field="start_date", title="UTC Time", formatter=bokeh.models.DateFormatter(format="%H:%M:%S")
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
