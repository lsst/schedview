import warnings
from types import MappingProxyType
from typing import Mapping

import astropy.units as u
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import seaborn
from astropy.coordinates import Angle, EarthLocation, HADec, get_body
from astropy.time import Time
from numpy.typing import NDArray
from rubin_scheduler.utils import Site


def mjd_to_local_solar_time(mjd: NDArray[np.number], location: EarthLocation) -> NDArray[np.number]:
    """Convart an array of MJD times to an times in local solar time.

    Parameters
    ----------
    mjd: `NDArray`,
        An array of MJDs
    location: `EarthLocation`
        Where to calculate midnight for.

    Returns
    -------
    local_solar_time: `NDArray`
        An array of times after local solar midnight.
    """
    ap_time = Time(mjd, format="mjd")
    ha_dec = HADec(obstime=ap_time, location=location)
    solar_ha_hours = get_body("sun", ap_time).transform_to(ha_dec).ha.hour
    local_solar_time = (solar_ha_hours + 12) % 24
    return local_solar_time


def _sexagesimal_formatter(hours, pos):
    return Angle(hours * u.hour).to_string(sep=":")


HMS_FORMATTER = mpl.ticker.FuncFormatter(_sexagesimal_formatter)


def make_categorical_hourglass(
    start_mjds: NDArray[np.number],
    duration: NDArray[np.number],
    values: NDArray,
    location: str | EarthLocation = Site("LSST").to_earth_location(),
    figure: None | mpl.figure.Figure = None,
    cmap: mpl.colors.Colormap = mpl.colors.ListedColormap(seaborn.color_palette("colorblind")),
    axes: mpl.axes.Axes | None = None,
    legend_kwargs: Mapping = MappingProxyType({}),
) -> mpl.axes.Axes:
    """Generate a categorical hourglass plot.

    Parameters
    ----------
    start_mjds: `NDArray[np.number]`
        An array of starting MJDs for the time segments.
    duration: `NDArray[np.number]`
        The duration in seconds of each time segment.
    values: `NDArray`
        Array of values for each time segment.
    location: `str` or `EarthLocation`, optional
        The geographic location from which to calculate solar time.
        Defaults to ``rubin_scheduler.utils.Site("LSST").to_earth_location()``.
    figure: `mpl.figure.Figure`, optional
        The matplotlib figure instance onto which the plot will be drawn,
        if not provided a new one will be created.
    cmap: `mpl.colors.Colormap`, optional
        The colormap to use for the plot.
        Defaults to a the seaborn colorblind palette.
    axes: `mpl.axes.Axes`, optional
        The Axes instance to use for plotting.
        If not provided, a new instance will be created.
    legend_kwargs : `Mapping`, optional
        Additional keyword arguments to pass to the `mpl.figure.Figure.legend`.

    Returns
    -------
    ax : `mpl.axes.Axes`
        The Matplotlib Axes object used for the hourglass.

    Examples
    --------

    If ``visits`` is the result of a query to the consdb:
    >>> fig = schedview.plot.hourglass.make_categorical_hourglass(
    ...     visits.obs_start_mjd,
    ...     visits.exp_time,
    ...     visits.band,
    ...     legend_kwargs = dict(
    ...         loc='upper center',
    ...         ncols=7,
    ...         bbox_to_anchor=(0.5, -0.1)
    ...     )
    ... )
    ...
    >>>

    """

    # **** Setting the vertical location of the bars *************

    # dayobs represented as a true (unmodified) julian date
    # note this true standard JD as the same rollover as dayobs.
    obs_jd: NDArray[np.int] = (start_mjds + 2400000.5).astype(int)

    # **** Setting the left edge of the bars *********************

    # Use the local solar time, so based on difference between LST and HA of
    # the sun, such that 0 is where the sun is at HA = -12 hours = -180 deg.
    earth_location: EarthLocation = EarthLocation.of_site(location) if isinstance(location, str) else location
    start_solar_hours = mjd_to_local_solar_time(start_mjds, location=earth_location)
    start_hours_after_midnight = np.where(start_solar_hours > 12, start_solar_hours - 24, start_solar_hours)

    # **** Setting the right edge of the bars ********************

    duration_hours = duration / (60 * 60)

    # **** Setting the colors of the bars ************************

    if cmap.N < len(np.unique(values)):
        warnings.warn(
            "More unique values than colors in the supplied color map, "
            + "so the same color will be used for multiple categories."
        )
    value_colors = {v: cmap(i) for i, v in enumerate(np.unique(values))}
    colors = np.array(np.vectorize(value_colors.get)(values)).T.tolist()

    # **** Prepare matplotlib figure and axes *********************

    if axes is None:
        figure = plt.figure() if figure is None else figure
        assert isinstance(figure, mpl.figure.Figure)
        axes = figure.add_axes((0, 0, 1, 1))
    else:
        figure = plt.figure() if figure is None else axes.get_figure()
    assert isinstance(axes, mpl.axes.Axes)
    assert isinstance(figure, mpl.figure.Figure)

    # **** actually make the bars *********************************

    axes.bar(
        start_hours_after_midnight,
        height=0.8,
        width=duration_hours,
        bottom=obs_jd - 0.4,
        color=colors,
        linewidth=0,
        align="edge",
    )

    # **** Put earlier dates on top ********************************
    axes.invert_yaxis()

    # **** Label the y ticks with ISO dates ************************
    yticks = axes.get_yticks()
    ytick_iso_labels = Time(yticks, format="jd").strftime("%Y-%m-%d")
    axes.set_yticks(yticks)
    axes.set_yticklabels(ytick_iso_labels)

    # **** Use HH:MM for x ticks ***********************************
    axes.xaxis.set_major_formatter(HMS_FORMATTER)

    # **** Build a legend ******************************************
    labels = value_colors.keys()
    handles = [mpl.patches.Patch(facecolor=value_colors[v], label=v) for v in labels]
    figure.legend(handles, labels, **legend_kwargs)

    return axes
