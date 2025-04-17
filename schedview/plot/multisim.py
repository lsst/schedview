from collections import namedtuple
from math import ceil
from typing import List, Literal

import bokeh
import bokeh.core.enums
import bokeh.models
import bokeh.plotting
import colorcet
import numpy as np
import pandas as pd
from sklearn.neighbors import KernelDensity

import schedview.plot

SimIndicators = namedtuple("SimIndicators", ("color_mapper", "color_dict", "marker_mapper", "hatch_dict"))


def generate_sim_indicators(sim_labels: List[str]) -> SimIndicators:
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

    if "Completed" in factors:
        # If one of the labels is "Completed," make sure it is black.
        palette = colorcet.palette["glasbey"][: num_sims - 1]
        palette.insert(list(factors).index("Completed"), "#000000")
    else:
        palette = colorcet.palette["glasbey"][:num_sims]
    color_mapper = bokeh.models.CategoricalColorMapper(factors=factors, palette=palette, name="simulation")

    color_dict = dict(zip(factors, palette))

    # Order them my how easily I can tell them apart when small
    all_markers = [
        "circle",
        "triangle",
        "inverted_triangle",
        "square",
        "diamond",
        "plus",
        "star",
        "square_pin",
        "triangle_pin",
        "hex_dot",
        "square_x",
        "circle_y",
        "diamond_cross",
        "triangle_dot",
        "circle_x",
        "square_cross",
        "diamond_dot",
        "square_dot",
        "star_dot",
        "circle_cross",
        "hex",
        "circle_dot",
    ]

    # If there are more factors than markers, repeat markers.
    if len(factors) > len(all_markers):
        all_markers = all_markers * int(ceil(len(factors) / len(all_markers)))

    # If one of the labels is "Completed", make sure it is marked with an
    # asterisk
    if "Completed" in factors:
        used_markers = all_markers[: num_sims - 1]
        used_markers.insert(list(factors).index("Completed"), "asterisk")
    else:
        used_markers = all_markers[:num_sims]

    marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=factors,
        markers=used_markers,
        name="simulation",
    )

    all_hatches = tuple(bokeh.core.enums.HatchPattern)[1:]
    # If there are more factors than hatch patterns, repeat hatch patterns.
    if len(factors) > len(all_hatches):
        all_hatches = all_hatches * int(ceil(len(factors) / len(all_hatches)))

    sim_hatch_dict = dict(zip(factors, all_hatches[: len(factors)]))

    return SimIndicators(color_mapper, color_dict, marker_mapper, sim_hatch_dict)


def plot_alt_airmass_vs_time(
    visits_ds: bokeh.models.ColumnDataSource,
    fig: bokeh.plotting.figure | None = None,
    scatter_user_kwargs: dict = {},
) -> bokeh.plotting.figure:
    """Plot alt and airmass vs. time for visits from multiple simulations.

    Parameters
    ----------
    visits_ds : `bokeh.models.ColumnDataSource`
        The table of visits.
    fig : `bokeh.plotting.figure` or `None`
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

    scatter_kwargs = dict(x="start_timestamp", y="altitude", legend_group="label", source=visits_ds)
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


def overplot_kernel_density_estimates(
    visits: pd.DataFrame,
    column: str,
    x_points: np.ndarray,
    bandwidth: float,
    colors: dict | None = None,
    hatches: dict | None = None,
    kernel: Literal["gaussian", "tophat", "epanechnikov", "exponential", "linear", "cosine"] = "epanechnikov",
    fig: bokeh.plotting.figure | None = None,
) -> bokeh.plotting.figure:
    """Overplot density estimates of distributions from different sims.

    Paramaters
    ----------
    visits : `pandas.DataFrame`
        The visits.
    column : `str`
        The column in the visits table of which to estimate the distribution.
    x_points : `np.ndarray`
        An array of points at which to compute the density estimates.
    bandwith : `float`
        The kernel bandwidth.
    colors : `dict`
        A mapping from sim label to bokeh color.
    hatches : `dict`
        A mapping from sim label to bokeh hatch pattern.
    kernel : `str`
        The kernel to use. See the sklearn.neighbors.KernelDensity
        documentation for the options and what they mean.
    fig: `bokeh.plotting.figure` or None
        The figure on which to plot. None creates a new figure.

    Returns
    -------
    fig: `bokeh.plotting.figure`
        The figure with the plot.
    """

    if fig is None:
        fig = bokeh.plotting.figure(width=1024, height=633, title=column)

    sim_labels = visits["label"].unique()
    for sim_label in sim_labels:
        this_sim_data = visits.set_index("label").loc[sim_label, column]
        if not isinstance(this_sim_data, pd.Series):
            # Maybe just one visit in a sim, in which case this_sim_data
            # will be a scalar.
            this_sim_data = pd.Series([this_sim_data])

        kde = KernelDensity(kernel=kernel, bandwidth=bandwidth).fit(this_sim_data.values[:, np.newaxis])
        prob_density = np.exp(kde.score_samples(x_points[:, np.newaxis]))

        varea_kwargs = dict(fill_alpha=0.1, legend_label=sim_label)

        if colors is not None:
            varea_kwargs["color"] = colors[sim_label]

        if hatches is not None:
            varea_kwargs["hatch_pattern"] = hatches[sim_label]

        fig.varea(x_points, prob_density, 0, **varea_kwargs)

    fig.add_layout(fig.legend[0], "below")
    return fig
