from types import MappingProxyType

import bokeh.layouts
import bokeh.models
import bokeh.plotting

__all__ = [
    "make_metric_line_plots",
]


SNAPSHOT_SCALAR_METRIC_FIGURE_NAME = "snapshot_scalar_metric_figure"
EXTRAPOLATED_SCALAR_METRIC_FIGURE_NAME = "extrapolated_scalar_metric_figure"


def make_metric_line_plots(
    metric_name,
    metric_values,
    snapshot_line_kwargs=MappingProxyType({"color": "black"}),
    snapshot_scatter_kwargs=MappingProxyType({"color": "black"}),
    baseline_line_kwargs=MappingProxyType({"color": "lightgreen", "width": 5}),
    baseline_ray_kwargs=MappingProxyType({"color": "lightgreen", "width": 5}),
    chimera_line_kwargs=MappingProxyType({"color": "black"}),
    chimera_scatter_kwargs=MappingProxyType({"color": "black"}),
):
    metric_values_ds = bokeh.models.ColumnDataSource(metric_values)

    metric_at_date_fig = bokeh.plotting.figure(
        title=f"{metric_name} at date",
        x_axis_label="Date",
        y_axis_label="Metric value",
        x_axis_type="datetime",
        name=SNAPSHOT_SCALAR_METRIC_FIGURE_NAME,
    )
    metric_at_date_fig.line(x="date", y="baseline", source=metric_values_ds, **baseline_line_kwargs)
    metric_at_date_fig.line(x="date", y="snapshot", source=metric_values_ds, **snapshot_line_kwargs)
    metric_at_date_fig.scatter(x="date", y="snapshot", source=metric_values_ds, **snapshot_scatter_kwargs)

    baseline_final_depth = metric_values.loc[metric_values.index.max(), "baseline"]
    chimera_metric_fig = bokeh.plotting.figure(
        title=f"{metric_name} extrapolated from date to end with baseline",
        x_axis_label="Date",
        y_axis_label="Metric value",
        x_axis_type="datetime",
        name=EXTRAPOLATED_SCALAR_METRIC_FIGURE_NAME,
    )
    chimera_metric_fig.ray(
        x=metric_values["date"].min(), y=baseline_final_depth, length=0, angle=0, **baseline_ray_kwargs
    )
    chimera_metric_fig.line(x="date", y="chimera", source=metric_values_ds, **chimera_line_kwargs)
    chimera_metric_fig.scatter(x="date", y="chimera", source=metric_values_ds, **chimera_scatter_kwargs)

    metric_figs = bokeh.layouts.row(metric_at_date_fig, chimera_metric_fig)
    return metric_figs
