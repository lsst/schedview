import calendar

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from rubin_sim import maf

from .util import mpl_fig_to_html


def plot_collapsed_monthly_hourglass_metric(
    metric_bundle,
    name,
    first_date,
    last_date,
    plotter_factory=maf.plots.MonthHourglassPlot,
) -> str:

    # Use plt.ioff to stop the jupyter notebook from showing the fig
    # natively, so we can use the collapseable html instead of rather
    # than in addition to it.
    with plt.ioff():
        # Set savefig.bbox to tight to avoid clipping off the legend.
        with mpl.rc_context({"savefig.bbox": "tight"}):
            figs_html = []

            # If we pass a list of plot_funcs to the MetricBundle, they all
            # get the same plot_dict, an so same title. We want different
            # titles for each month, so iterate here:
            for month_timestamp in pd.date_range(
                pd.Timestamp(first_date).replace(day=1), last_date, freq="MS"
            ):
                year, month = month_timestamp.year, month_timestamp.month
                title = f"{name} for {calendar.month_name[month]}, {year}"
                metric_bundle.plot_dict["title"] = title
                metric_bundle.plot_funcs = [plotter_factory(month, year)]
                these_figs = metric_bundle.plot()
                assert len(these_figs) == 1
                this_fig = next(iter(these_figs.values()))
                figs_html.append(mpl_fig_to_html(this_fig, summary=f"Hourglass of {title}"))

    all_figs_html = "\n".join(figs_html)
    return all_figs_html
