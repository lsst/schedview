import bokeh
import numpy as np
from astropy.time import Time

from .colors import PLOT_FILTER_CMAP


def create_cadence_plot(
    nightly_totals, start_dayobs_mjd, end_dayobs_mjd, targets=None, cmap=PLOT_FILTER_CMAP, user_plot_kwargs={}
):
    if targets is None:
        targets = tuple(nightly_totals.index.unique())

    date_factors = [Time(mjd, format="mjd").iso[:10] for mjd in np.arange(start_dayobs_mjd, end_dayobs_mjd)]
    band_factors = cmap.transform.factors

    cadence_plots = []

    plot_kwargs = {
        "x_range": bokeh.models.FactorRange(factors=date_factors),
        "frame_height": 150,
        "frame_width": 1024,
        "title_location": "left",
    }
    plot_kwargs.update(user_plot_kwargs)

    for target in targets:
        last_plot = len(cadence_plots) == len(targets) - 1

        plot_kwargs["title"] = target
        plot_kwargs["x_axis_location"] = "below" if last_plot else None
        this_plot = bokeh.plotting.figure(**plot_kwargs)

        this_plot.xaxis.major_label_orientation = "vertical"

        kwargs = {"legend_label": band_factors} if last_plot else {}
        this_plot.vbar_stack(
            stackers=band_factors,
            x="day_obs_iso8601",
            width=0.9,
            source=nightly_totals.loc[target, :],
            color=cmap.transform.palette,
            fill_alpha=0.3,
            **kwargs,
        )

        if last_plot:
            legend = this_plot.legend[0]
            legend.orientation = "horizontal"
            this_plot.add_layout(legend, "below")

        cadence_plots.append(this_plot)

    full_cadence_figure = bokeh.layouts.column(cadence_plots)

    return full_cadence_figure
