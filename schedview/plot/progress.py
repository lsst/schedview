"""Standalone scalar metric progress plots with browser-only selection."""

import json
import warnings
from collections.abc import Mapping
from types import MappingProxyType

import bokeh.core.enums
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import numpy as np
import pandas as pd
from bokeh.util.compiler import JavaScript

from schedview.collect.progress import SummaryMetrics, validate_summary_metrics
from schedview.plot.colors import make_band_cmap

__all__ = ["make_metric_line_plots", "make_summary_progress_plot"]

SNAPSHOT_SCALAR_METRIC_FIGURE_NAME = "snapshot_scalar_metric_figure"
EXTRAPOLATED_SCALAR_METRIC_FIGURE_NAME = "extrapolated_scalar_metric_figure"
SOURCE_STYLES = {"consdb": (1, 1.0), "chimera": (2, 0.8), "baseline": (3, 0.6)}


# Bokeh omits underscore-prefixed classes from notebook resource bundles.
class ProgressLinearScale(bokeh.models.LinearScale):
    """Map finite extremes without rescaling the recorded values."""

    __implementation__ = JavaScript("""
import {LinearScale} from "models/scales/linear_scale"

export class ProgressLinearScale extends LinearScale {
    static __name__ = "ProgressLinearScale";
    get s_compute() {
        const {source_range: source, target_range: target} = this;
        if (Number.isFinite(source.end - source.start)) return super.s_compute;
        const start = source.start / 2;
        const span = source.end / 2 - start;
        return x => target.start + ((x / 2 - start) / span) * (target.end - target.start);
    }
    get s_invert() {
        const {source_range: source, target_range: target} = this;
        if (Number.isFinite(source.end - source.start)) return super.s_invert;
        return sx => {
            const fraction = (sx - target.start) / (target.end - target.start);
            return (1 - fraction) * source.start + fraction * source.end;
        };
    }
}
""")


def make_metric_line_plots(
    metric_name: str,
    metric_values: pd.DataFrame,
    snapshot_line_kwargs: Mapping = MappingProxyType({"color": "black"}),
    snapshot_scatter_kwargs: Mapping = MappingProxyType({"color": "black"}),
    baseline_line_kwargs: Mapping = MappingProxyType({"color": "lightgreen", "width": 5}),
    baseline_ray_kwargs: Mapping = MappingProxyType({"color": "lightgreen", "width": 5}),
    chimera_line_kwargs: Mapping = MappingProxyType({"color": "black"}),
    chimera_scatter_kwargs: Mapping = MappingProxyType({"color": "black"}),
) -> bokeh.layouts.Row:
    """Create the existing paired snapshot/extrapolated scalar metric plots.

    This older API takes computed baseline/snapshot/chimera columns, not MAF
    summary records. The interactive summary API does not use its baseline ray.
    """
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
    return bokeh.layouts.row(metric_at_date_fig, chimera_metric_fig)


def make_summary_progress_plot(summary_metrics: SummaryMetrics | str) -> bokeh.models.UIElement:
    """Create a standalone interactive plot of scalar MAF summary records.

    Parameters
    ----------
    summary_metrics : pandas.DataFrame or str
        Validated summary records, including filtered copies, or a JSON URL.
        URLs are fetched once on page load and resolved against the page URL.
        External pages must be HTTP(S)-served with same-origin or CORS access.

    Returns
    -------
    bokeh.models.UIElement
        Four cascading selectors, status, figure, and three informational
        legends. Embedded records require no companion data file or server.
    """
    if isinstance(summary_metrics, str):
        records, url = None, summary_metrics
    else:
        validate_summary_metrics(summary_metrics)
        clean = summary_metrics.copy()
        missing_count = int(clean["summary_value"].isna().sum())
        nonfinite_count = int(clean["summary_value"].isin([np.inf, -np.inf]).sum())
        if missing_count or nonfinite_count:
            warnings.warn(
                f"Plotting {missing_count + nonfinite_count} missing/non-finite summary measurements "
                f"as gaps ({missing_count} missing, {nonfinite_count} non-finite)",
                UserWarning,
                stacklevel=2,
            )
        clean["summary_value"] = clean["summary_value"].replace([np.inf, -np.inf], np.nan)
        records = json.loads(
            clean.to_json(orient="records", date_format="epoch", date_unit="ms", double_precision=15)
        )
        url = None

    metric = bokeh.models.Select(title="Metric", options=[], value="", name="progress_metric")
    source = bokeh.models.MultiSelect(title="Source", options=[], value=[], name="progress_source")
    label = bokeh.models.MultiSelect(title="Metric info label", options=[], value=[], name="progress_label")
    summary = bokeh.models.MultiSelect(title="Summary metric", options=[], value=[], name="progress_summary")
    status = bokeh.models.Div(text="Loading summary metrics...", name="progress_status")
    lines = bokeh.models.ColumnDataSource(
        dict(xs=[], ys=[], color=[], width=[], alpha=[], dash=[]), name="progress_lines"
    )
    points = bokeh.models.ColumnDataSource(
        dict(
            date=[],
            summary_value=[],
            run_name=[],
            metric_name=[],
            metric_info_label=[],
            summary_metric=[],
            color=[],
        ),
        name="progress_points",
    )
    plot = bokeh.plotting.figure(
        height=440,
        sizing_mode="stretch_width",
        x_axis_type="datetime",
        x_axis_label="Observing date",
        y_axis_label="Summary value",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        x_range=bokeh.models.Range1d(0, 86400000),
        y_range=bokeh.models.Range1d(0, 1),
        name="summary_progress_figure",
    )
    plot.y_scale = ProgressLinearScale()
    plot.multi_line(
        xs="xs",
        ys="ys",
        source=lines,
        line_color="color",
        line_width="width",
        line_alpha="alpha",
        line_dash="dash",
    )
    scatter = plot.scatter(
        x="date",
        y="summary_value",
        source=points,
        color="color",
        size=8,
        alpha=0.6,
        hover_color="black",
        hover_alpha=1.0,
    )
    plot.add_tools(
        bokeh.models.HoverTool(
            renderers=[scatter],
            tooltips=[
                ("Run", "@run_name"),
                ("Metric", "@metric_name"),
                ("Label", "@metric_info_label"),
                ("Summary", "@summary_metric"),
                ("Value", "@summary_value"),
            ],
        )
    )
    plot.xaxis.formatter = bokeh.models.DatetimeTickFormatter(days="%Y-%m-%d", months="%Y-%m", years="%Y")
    # Informational HTML legends never introduce reference data.
    legends = [bokeh.models.Div(name=f"progress_{kind}_legend") for kind in ("source", "band", "summary")]
    cmap = make_band_cmap(bands=("u", "g", "r", "i", "z", "y", "all"))["transform"]
    colors = dict(zip(cmap.factors, cmap.palette))
    callback = bokeh.models.CustomJS(
        args=dict(
            metric=metric,
            source=source,
            label=label,
            summary=summary,
            status=status,
            lines=lines,
            points=points,
            plot=plot,
            legends=legends,
            records=records,
            url=url,
            colors=colors,
            styles=SOURCE_STYLES,
            dashes=list(bokeh.core.enums.LineDash),
        ),
        code=_PROGRESS_CALLBACK,
    )
    for control in (metric, source, label, summary):
        control.js_on_change("value", callback)
    # DocumentReady is a document event, not dispatched to figure callbacks.
    plot.js_on_change("inner_width", callback)
    return bokeh.layouts.column(
        bokeh.layouts.row(metric, source, label, summary, sizing_mode="stretch_width"),
        status,
        plot,
        *legends,
        sizing_mode="stretch_width",
    )


_PROGRESS_CALLBACK = r"""
const canonical = value => value == null || value === "" ? "" : value;
const labelKey = value => JSON.stringify(canonical(value));
const sorted = values => [...new Set(values)].sort();
const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);

export default async function(args, changed) {
    const {metric, source, label, summary, status, lines, points, plot, legends,
           records, url, colors, styles, dashes} = args;
    // Concurrent CustomJS compilation can yield multiple module instances.
    // The model survives all of them; claim initialization before any await.
    const state = status._progress_state ??= {
        data: null, busy: false, started: false, slots: new Map(),
        previousSummaries: [], selection: null,
    };
    const slots = state.slots;
    const selectionKey = () => JSON.stringify([metric.value, source.value, label.value, summary.value]);
    if (state.started && (changed === plot || selectionKey() === state.selection)) return;
    if (state.busy) return;
    state.busy = true;
    try {
        let initial = false;
        if (!state.started) {
            state.started = true;
            initial = true;
            for (const control of [metric, source, label, summary]) control.disabled = true;
            if (url !== null) {
                status.text = `Loading ${escape(url)}...`;
                const response = await fetch(url, {cache: "no-store"});
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                state.data = await response.json();
            } else state.data = records;
        }
        const data = state.data;
        if (data === null) return;
        const metrics = sorted(data.map(row => row.metric_name));
        metric.options = metrics;
        if (initial) metric.value = metrics[0] ?? "";
        metric.disabled = metrics.length === 0;
        let rows = data.filter(row => row.metric_name === metric.value);
        const cascade = (control, options, upstreamChanged, cap = Infinity) => {
            const valid = control.value.filter(value => options.includes(value));
            control.options = options;
            control.disabled = options.length === 0;
            if (initial || upstreamChanged) {
                control.value = valid.length ? valid.slice(0, cap) : options.slice(0, cap);
            }
        };
        cascade(source, sorted(rows.map(row => row.visit_source)), changed === metric);
        rows = rows.filter(row => source.value.includes(row.visit_source));
        const labels = sorted(rows.map(row => labelKey(row.metric_info_label)));
        const validLabels = label.value.filter(value => labels.includes(value));
        label.options = labels.map(key => [key, JSON.parse(key) === "" ? "(no label)" : key]);
        label.disabled = labels.length === 0;
        if (initial || changed === metric || changed === source) {
            label.value = validLabels.length ? validLabels : labels;
        }
        rows = rows.filter(row => label.value.includes(labelKey(row.metric_info_label)));
        cascade(summary, sorted(rows.map(row => row.summary_metric)),
                changed === metric || changed === source || changed === label, dashes.length);
        let limited = false;
        if (summary.value.length > dashes.length) {
            const survivors = state.previousSummaries.filter(value => summary.value.includes(value));
            summary.value = [...survivors, ...summary.value.filter(value => !survivors.includes(value))]
                .slice(0, dashes.length);
            limited = true;
        }
        state.previousSummaries = [...summary.value];
        for (const name of slots.keys()) if (!summary.value.includes(name)) slots.delete(name);
        for (const name of summary.value) {
            if (!slots.has(name)) {
                const used = new Set(slots.values());
                slots.set(name, dashes.findIndex((_, index) => !used.has(index)));
            }
        }
        rows = rows.filter(row => summary.value.includes(row.summary_metric));
        const groups = new Map();
        for (const row of rows) {
            const key = JSON.stringify([canonical(row.metric_name), canonical(row.metric_info_label),
                                        canonical(row.summary_metric), row.visit_source]);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(row);
        }
        const lineData = {xs: [], ys: [], color: [], width: [], alpha: [], dash: []};
        const pointData = {date: [], summary_value: [], run_name: [], metric_name: [],
                           metric_info_label: [], summary_metric: [], color: []};
        const finite = row => row.summary_value !== null && Number.isFinite(row.summary_value);
        for (const group of groups.values()) {
            group.sort((a, b) => a.date - b.date);
            const first = group[0];
            const color = colors[first.band];
            lineData.xs.push(group.map(row => row.date));
            lineData.ys.push(group.map(row => finite(row) ? row.summary_value : NaN));
            lineData.color.push(color);
            lineData.width.push(styles[first.visit_source][0]);
            lineData.alpha.push(styles[first.visit_source][1]);
            lineData.dash.push(dashes[slots.get(first.summary_metric)]);
            for (const row of group.filter(finite)) {
                for (const field of Object.keys(pointData)) {
                    pointData[field].push(field === "color" ? color : row[field]);
                }
            }
        }
        lines.data = lineData;
        points.data = pointData;
        const extent = (values, fallback, singleton) => {
            if (!values.length) return fallback;
            let low = Infinity, high = -Infinity;
            for (const value of values) {low = Math.min(low, value); high = Math.max(high, value);}
            const pad = low === high ? singleton(low) : high * 0.05 - low * 0.05;
            return [Math.max(-Number.MAX_VALUE, low - pad), Math.min(Number.MAX_VALUE, high + pad)];
        };
        for (const [range, bounds] of [
            [plot.x_range, extent(pointData.date, [0, 86400000], () => 86400000)],
            [plot.y_range, extent(pointData.summary_value, [0, 1],
                                 value => Math.max(Math.abs(value)*0.05, 1))]
        ]) {
            [range.start, range.end] = bounds;
            [range.reset_start, range.reset_end] = bounds;
        }
        plot.title.text = metric.value || "Summary progress";
        const swatch = (text, color, width = 2, alpha = 1, dash = "solid") =>
            `<span style="display:inline-block;margin-right:18px"><svg width="38" height="14">` +
            `<line x1="0" y1="7" x2="38" y2="7" stroke="${color}" stroke-width="${width}" ` +
            `opacity="${alpha}" stroke-dasharray="${({solid:"", dashed:"3 2", dotted:"2 1",
            dotdash:"2 4 6 4", dashdot:"6 4 2 4"})[dash] ?? ""}"/></svg> ${escape(text)}</span>`;
        legends[0].text = "<b>Source</b> " + sorted(rows.map(row => row.visit_source))
            .map(name => swatch(name, "black", ...styles[name])).join("");
        legends[1].text = "<b>Band</b> " + sorted(rows.map(row => row.band))
            .map(name => swatch(name, colors[name])).join("");
        legends[2].text = "<b>Summary</b> " + summary.value
            .map(name => swatch(name, "black", 2, 1, dashes[slots.get(name)])).join("");
        const noData = !pointData.date.length;
        const limitText = `Select at most ${dashes.length} summaries; deselect one to replace it.`;
        const countText = noData ? "No finite data for the current selection." :
            `${pointData.date.length} finite measurements.`;
        const gaps = rows.filter(row => !finite(row)).length;
        status.text = (limited ? `Selection limit: ${limitText} ` : "") + countText +
            (gaps ? ` ${gaps} missing/non-finite measurements shown as gaps.` : "") +
            (summary.options.length > dashes.length && !limited ? ` ${limitText}` : "") +
            (url !== null ? ` Source: ${escape(url)}` : "");
    } catch (error) {
        lines.data = {xs: [], ys: [], color: [], width: [], alpha: [], dash: []};
        points.data = {date: [], summary_value: [], run_name: [], metric_name: [],
                       metric_info_label: [], summary_metric: [], color: []};
        for (const legend of legends) legend.text = "";
        status.text = `Failed to load ${escape(url ?? "embedded records")}: ${escape(error.message)}`;
        for (const control of [metric, source, label, summary]) control.disabled = true;
    } finally {
        // CustomJS.execute awaits compilation even for cached modules. Ignore
        // queued callbacks from our own setters after this update has settled.
        state.selection = selectionKey();
        state.busy = false;
    }
}
"""
