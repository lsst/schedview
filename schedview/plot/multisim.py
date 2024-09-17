from collections import namedtuple
from math import ceil
from typing import List

import bokeh
import bokeh.core.enums
import bokeh.models
import bokeh.plotting
import colorcet

import schedview.plot

SimIndicators = namedtuple("SimIndicators", ("color_mapper", "color_dict", "marker_mapper", "hatch_dict"))


def generate_sim_indicators(sim_labels: List[str]):
    """Generate a tuple of simulation indicators for bokeh.

    Parameters
    ----------
    sim_labels: `list` [`str`]
        A list of simulation labels.

    Returns
    -------
    sim_indicators: `SimIndicators`
        A named tuple with:

        ``color_mapper``
            The bokeh color mapper to map sim labels to colors.
        ``color_dict``
            A python dictionary representing the same mapping as
            ``color_mapper``, above.
        ``marker_mapper``
            The bokeh mapper to map sim labels to bokeh markers.
        ``hatch_dict``
            A python dict to map sim labels to bokeh hatch styles.
    """
    num_sims = len(sim_labels)
    factors = sim_labels

    all_colors = colorcet.palette["glasbey"]
    # If there are more factors than colors, repeat colors.
    if len(factors) > len(all_colors):
        all_colors = all_colors * int(ceil(len(factors) / len(all_colors)))

    palette = colorcet.palette["glasbey"][:num_sims]
    color_mapper = bokeh.models.CategoricalColorMapper(factors=factors, palette=palette, name="simulation")

    color_dict = dict(zip(factors, palette))

    # Some bokeh symbols have the same outer shape but different inner
    # markings, but these are harder to distinguish, so put them at the end.
    all_markers = [m for m in bokeh.core.enums.MarkerType if "_" not in m] + [
        m for m in bokeh.core.enums.MarkerType if "_" in m
    ]
    # dot is hard to see
    all_markers.remove("dot")
    # If there are more factors than markers, repeat markers.
    if len(factors) > len(all_markers):
        all_markers = all_markers * int(ceil(len(factors) / len(all_markers)))

    marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=factors,
        markers=all_markers[:num_sims],
        name="simulation",
    )

    all_hatches = tuple(bokeh.core.enums.HatchPattern)[1:]
    # If there are more factors than hatch patterns, repeat hatch patterns.
    if len(factors) > len(all_hatches):
        all_hatches = all_hatches * int(ceil(len(factors) / len(all_hatches)))

    sim_hatch_dict = dict(zip(factors, all_hatches[: len(factors)]))

    return SimIndicators(color_mapper, color_dict, marker_mapper, sim_hatch_dict)


def plot_alt_airmass_vs_time(visits_ds, fig=None, scatter_user_kwargs={}):
    """Plot alt and airmass vs. time for visits from multiple simulations.

    Parameters
    ----------
    visits_ds : `bokeh.models.ColumnDataSource`
        The table of visits.
    fig : `bokeh.plotting.Figure` or `None`
        The bokeh Figure to use, or None to create one
    scatter_user_kwargs : `dict`
        Any additional parameters to be passed
        to `bokeh.plotting.Figure.scatter`.

    Returns
    -------
    fig : `bokeh.plotting.Figure`
        The figure with the plot.
    """

    if fig is None:
        fig = bokeh.plotting.figure(
            title="Altitude",
            x_axis_label="Time (UTC)",
            y_axis_label="Altitude",
            frame_width=1024,
            frame_height=633,
        )

    scatter_kwargs = dict(x="start_date", y="altitude", legend_group="label", source=visits_ds)
    scatter_kwargs.update(scatter_user_kwargs)
    fig.scatter(**scatter_kwargs)

    fig.extra_y_ranges = {"airmass": fig.y_range}
    fig.add_layout(bokeh.models.LinearAxis(), "right")
    fig.yaxis[1].ticker.desired_num_ticks = fig.yaxis[0].ticker.desired_num_ticks
    fig.yaxis[1].formatter = schedview.plot.nightly.make_airmass_tick_formatter()
    fig.yaxis[1].minor_tick_line_alpha = 0
    fig.yaxis[1].axis_label = "Airmass"

    fig.xaxis[0].ticker = bokeh.models.DatetimeTicker()
    fig.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    fig.add_layout(fig.legend[0], "below")
    return fig
