import bokeh
import bokeh.models
import bokeh.plotting
import bokeh.transform
from astropy.time import Time
from bokeh.models import ColumnDataSource

import schedview.compute.nightreport
import schedview.plot.nightreport


def _make_log_message_data_source(messages, name="Log messages", html_formatter=None) -> ColumnDataSource:
    # Create a bokeh data source from the list of messages
    ds_dict = {}
    for key in messages[0]:
        if key in ("date_begin", "date_end"):
            ds_dict[key] = Time([m[key] for m in messages]).datetime64
        else:
            ds_dict[key] = [m[key] for m in messages]
        if html_formatter is not None:
            ds_dict["html"] = [html_formatter(m) for m in messages]
        else:
            ds_dict["html"] = [f"<pre>{m['message_text']}</pre>" for m in messages]
        ds_dict["timeline"] = [name] * len(messages)
    messages_ds = ColumnDataSource(data=ds_dict)
    return messages_ds


def add_timeline_scatter_renderer(
    plot, source, factor_column="timeline", time_column="date_begin", jitter=False, **kwargs
):
    # Make sure this timeline is included in the y range
    try:
        factors = plot.y_range.factors
    except AttributeError:
        raise ValueError("supplied plot instance y_range must be FactorRange.")

    needed_factors = sorted(list(set(source.data[factor_column])))
    for needed_factor in needed_factors:
        if needed_factor not in factors:
            factors.append(needed_factor)

    plot.y_range.update(factors=factors)

    renderer = plot.scatter(
        x=time_column,
        y=(
            bokeh.transform.jitter(factor_column, width=0.05, range=plot.y_range) if jitter else factor_column
        ),
        source=source,
        **kwargs,
    )

    return renderer


def make_timeline_scatterplots(log_messages=None, visits=None, visits_column="seeingFwhmEff", jitter=False):
    timeline_plot = bokeh.plotting.figure(
        x_axis_type="datetime",
        y_range=bokeh.models.FactorRange(),
        tooltips="@html",
    )

    if log_messages is not None:
        log_message_source = _make_log_message_data_source(
            log_messages, html_formatter=schedview.plot.nightreport.narrative_message_html
        )
        add_timeline_scatter_renderer(timeline_plot, log_message_source, jitter=jitter)

    if visits is not None and len(visits) > 0:
        visit_plot = bokeh.plotting.figure(
            x_range=timeline_plot.x_range, y_axis_label=visits_column, x_axis_label="Time (UTC)", name="visit"
        )
        param_vs_time_ui_element = schedview.plot.plot_visit_param_vs_time(
            visits, visits_column, show_column_selector=True, plot=visit_plot
        )
        ui_element = bokeh.layouts.gridplot([[timeline_plot, param_vs_time_ui_element]])
    else:
        ui_element = timeline_plot

    return ui_element
