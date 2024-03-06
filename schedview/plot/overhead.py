from io import StringIO
from xml.etree import ElementTree as et

import bokeh
import numpy as np

from .colors import PLOT_FILTER_CMAP


def create_overhead_summary_table(overhead_summary, html=True):
    """Make a formatted table from an overhead summary dictionary

    Parameters
    ----------
    `overhead_summary`: `dict`
        A dictionary of summary values, as computed by
        `schedview.compute.visits.compute_overhead_summary`
    `html`: `bool`
        Format the table with html? Defaults to True

    Returns
    -------
    `summary` : `str`
        Formatted summary.
    """
    stat_name = {
        "relative_start_time": "Open shutter of first exposure",
        "relative_end_time": "Close shutter time of last exposure",
        "total_time": "Total wall clock time",
        "num_exposures": "Number of exposures",
        "total_exptime": "Total open shutter time",
        "mean_gap_time": "Mean gap time",
        "median_gap_time": "Median gap time",
    }
    stat_str_template = {
        "relative_start_time": "{:5.2f} minutes before 12 degree evening twilight",
        "relative_end_time": "{:5.2f} minutes before 12 degree morning twilight",
        "total_time": "{:4.2f} hours",
        "num_exposures": "{}",
        "total_exptime": "{:4.2f} hours",
        "mean_gap_time": "{:7.2f} seconds",
        "median_gap_time": "{:7.2f} seconds",
    }

    with StringIO() as result_io:
        if html:
            summary = et.Element("dl")
            for stat_key in overhead_summary:
                name_el = et.Element("dt")
                name_el.text = stat_name[stat_key]
                value_el = et.Element("dd")
                value_el.text = stat_str_template[stat_key].format(overhead_summary[stat_key])
                summary.append(name_el)
                summary.append(value_el)
            et.ElementTree(summary).write(result_io, encoding="unicode", method="html")
        else:
            for stat_key in overhead_summary:
                print(
                    stat_name[stat_key],
                    ": ",
                    stat_str_template[stat_key].format(overhead_summary[stat_key]),
                    file=result_io,
                )

        result = result_io.getvalue()

    return result


def create_overhead_histogram(visits, bins=np.arange(30), plot=None, **kwargs):
    """Create a histogram of visit overhead times.

    Paramaters
    ----------
    `visits` : `pandas.DataFrame`
        The table of visits, with overhead data (see add_overhead)
    `bins` : `numpy.ndarray`
        Bin locations for the histogram.
    `plot` : `bokeh.models.plots.Plot` or None
        The figure on which to plot the histogram. None creates a new
        figure. Defaults to None.

    Returns
    -------
    `plot` : `bokeh.models.plots.Plot`
        The figure with the histogram.
    """

    hist, edges = np.histogram(visits.overhead, density=False, bins=bins)
    if plot is None:
        plot = bokeh.plotting.figure(
            title="Overhead", x_axis_label="Overhead (seconds)", y_axis_label="Number of visits"
        )

    quad_kwargs = {"line_color": "white"}
    quad_kwargs.update(kwargs)

    plot.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:], **quad_kwargs)

    return plot


def plot_overhead_vs_slew_distance(visits, plot=None, **kwargs):
    """Plot visit overhead times.

    Paramaters
    ----------
    `visits` : `pandas.DataFrame`
        The table of visits, with overhead data (see add_overhead)
    `bins` : `numpy.ndarray`
        Bin locations for the histogram.
    `plot` : `bokeh.models.plots.Plot` or None
        The figure on which to plot the histogram. None creates a new
        figure. Defaults to None.

    Returns
    -------
    `plot` : `bokeh.models.plots.Plot`
        The figure with the histogram.
    """

    if plot is None:
        plot = bokeh.plotting.figure(
            title="Overhead vs. slew distance",
            y_axis_label="overhead (sec.)",
            x_axis_label="slew distance (deg.)",
        )

    circle_kwargs = {"color": PLOT_FILTER_CMAP, "fill_alpha": 0.3}
    circle_kwargs.update(kwargs)

    for band in PLOT_FILTER_CMAP.transform.factors:
        these_visits = visits.query(f'filter == "{band}"')

        if len(these_visits) > 0:
            plot.circle(
                x="slewDistance", y="overhead", source=these_visits, legend_label=band, **circle_kwargs
            )

    legend = plot.legend[0]
    legend.orientation = "horizontal"
    plot.add_layout(legend, "below")

    return plot
