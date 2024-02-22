import bokeh
import hvplot
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.collect.opsim
import schedview.compute.astro

from .colors import PLOT_FILTER_CMAP


def plot_visits(visits):
    """Instantiate an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`

    Returns
    -------
    figure : `hvplot.ui.hvDataFrameExplorer`
        The figure itself.
    """
    visit_explorer = hvplot.explorer(visits, kind="scatter", x="start_date", y="airmass", by=["note"])
    return visit_explorer


def create_visit_explorer(visits, night_date, observatory=None, timezone="Chile/Continental"):
    """Create an explorer to interactively examine a set of visits.

    Parameters
    ----------
    visits : `str` or `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`,
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
        visits = schedview.collect.opsim.read_opsim(visits, Time(start_time).iso, Time(end_time).iso)

    # Plot
    data = {"visits": visits}
    visit_explorer = plot_visits(visits)

    return visit_explorer, data


def plot_visit_param_vs_time(visits, column_name, plot=None, **kwargs):
    """Plot a column in the visit table vs. time.

    Parameters
    ----------
    `visits`: `pandas.DataFrame`
        One row per visit, as created by `schedview.collect.opsim.read_opsim`.
    `column_name`: `str`
        The name of the column to plot against time.
    `plot`: `bokeh.models.plots.Plot` or None
        The figure on which to plot the visits. None creates a new
        figure. Defaults to None.

    Returns
    -------
    `plot` : `bokeh.models.plots.Plot`
        The figure with the plot.
    """
    if plot is None:
        plot = bokeh.plotting.figure(y_axis_label=column_name, x_axis_label="Time (UTC)")

    circle_kwargs = {"fill_alpha": 0.3}
    circle_kwargs.update(kwargs)

    for band in PLOT_FILTER_CMAP.transform.factors:
        these_visits = visits.query(f'filter == "{band}"')
        if len(these_visits) > 0:
            plot.circle(
                x="start_date",
                y=column_name,
                color=PLOT_FILTER_CMAP,
                source=these_visits,
                legend_label=band,
                **circle_kwargs,
            )

    plot.xaxis[0].formatter = bokeh.models.DatetimeTickFormatter(hours="%H:%M")

    legend = plot.legend[0]
    legend.orientation = "horizontal"
    plot.add_layout(legend, "below")
    return plot
