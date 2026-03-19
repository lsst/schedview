from typing import List, Optional, Tuple

import bokeh
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import numpy as np
import pandas as pd

from schedview.plot.colors import make_band_cmap


def plot_obs_vs_sim_time(
    offsets: pd.DataFrame, tooltips: List[Tuple[str, str]], plot: Optional[bokeh.plotting.figure] = None
) -> bokeh.models.UIElement:
    """
    Plot observation times vs simulation times for visits.

    Parameters
    ----------
    offsets : `pd.DataFrame`
        DataFrame containing visit timing information with columns including
        'obs_time', 'sim_time', 'sim_index', and 'label' as well as any
        columns needed for the tooltips.
    tooltips : `List[Tuple[str, str]]`
        List of tuples defining the tooltip content for hover interactions.
    plot : `bokeh.plotting.figure`, optional
        Existing bokeh figure to use. If ``None``, a new figure is created.

    Returns
    -------
    obs_vs_sim_time_plot : `bokeh.models.UIElement`
        A bokeh UI element containing the simulation selector and the plot.
    """
    if plot is None:
        plot = bokeh.plotting.figure(frame_width=1024, frame_height=512)

    offsets_plot_df = offsets.reset_index().set_index("sim_index")
    offsets_plot_df.reset_index(inplace=True)
    default_sim_id = offsets_plot_df.sim_index.min()
    offsets_plot_df["sim_alpha"] = np.where(offsets_plot_df.sim_index == default_sim_id, 1, 0)

    source = bokeh.models.ColumnDataSource(offsets_plot_df)

    matching_line = bokeh.models.Slope(gradient=1, y_intercept=0, line_color="gray", line_width=1)
    plot.add_layout(matching_line)

    scatter_renderer = plot.scatter(
        "sim_time", "obs_time", color=make_band_cmap("band"), alpha="sim_alpha", source=source
    )
    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
    plot.xaxis[0].axis_label = "visit start time in simulation"
    plot.yaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")
    plot.yaxis[0].axis_label = "visit start time as completed"

    hover_tool = bokeh.models.HoverTool(
        renderers=[scatter_renderer],
        tooltips=tooltips,
        formatters={"@obs_time": "datetime", "@sim_time": "datetime"},
    )
    plot.add_tools(hover_tool)

    if "label" not in source.column_names:
        raise ValueError("A sim selector needs the label column")
    sim_labels = offsets.groupby("sim_index")["label"].first().to_frame()
    default_sim = sim_labels.loc[default_sim_id, "label"]
    sim_selector = bokeh.models.Select(
        value=default_sim, options=sim_labels.label.to_list(), name="simselect"
    )

    sim_selector_callback = bokeh.models.CustomJS(
        args={"source": source},
        code="""
            for (let i = 0; i < source.data['label'].length; i++) {
                if (['All', source.data['label'][i]].includes(this.value)) {
                    source.data['sim_alpha'][i] = 1.0;
                } else {
                    source.data['sim_alpha'][i] = 0.0;
                }
            }
            source.change.emit()
        """,
    )
    sim_selector.js_on_change("value", sim_selector_callback)

    ui_element = bokeh.layouts.column([sim_selector, plot])
    return ui_element
