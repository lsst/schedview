"""Standalone scalar metric progress plots with browser-only selection."""

import json
import warnings
from collections.abc import Mapping
from types import MappingProxyType

import bokeh.core.enums
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import numpy as np
import pandas as pd
from bokeh.events import DocumentReady

from schedview.collect.progress import SummaryMetrics, validate_summary_metrics
from schedview.plot.colors import make_band_cmap

__all__ = ["SOURCE_STYLES", "make_metric_line_plots", "make_summary_progress_plot"]

SOURCE_STYLES: dict[str, tuple[int, float]] = {
    "consdb": (1, 1.0),
    "chimera": (3, 0.6),
    "baseline": (5, 0.3),
}
"""Source -> (width in pixels, alpha), shared by lines and legend swatches."""

_PROGRESS_STARTUP = "schedview-progress-startup"
"""Tag/name linking each plot's status model to the document dispatcher."""

_PROGRESS_DOCUMENT_READY = """
export default function(args, document) {
    const visited = new Set();
    for (const root of document.roots()) {
        for (const model of root.references()) {
            if (visited.has(model) || !model.tags.includes("__STARTUP_TAG__")) continue;
            visited.add(model);
            for (const callback of model.js_event_callbacks.document_ready ?? []) {
                // Start every plot independently, without waiting for another fetch.
                void callback.execute(document);
            }
        }
    }
}
""".replace("__STARTUP_TAG__", _PROGRESS_STARTUP)


# Browser-side load/update transaction, shared by document startup and all
# four selector controls.
#
# What this string is
# -------------------
# JavaScript source for the Bokeh CustomJS callback built in
# make_summary_progress_plot below. Python never executes it: Bokeh embeds
# the text in the generated page or notebook output, and the browser runs it.
# It is written as a JavaScript module whose default export is an async
# function. Bokeh calls that function with two positional arguments:
#
#   args     An object (dict-like, attribute access) holding everything
#            passed to CustomJS(args=...): the four selector models, the
#            status Div, the two ColumnDataSources, the figure, the legend
#            Divs, the embedded records (or null), the external JSON URL (or
#            null), and the band-color, source-style, and named-dash tables.
#            The `const {...} = args` line at the top of the function unpacks
#            these into local names.
#   changed  The object that triggered the call: the selector whose value
#            changed, or the document itself at startup. Tests such as
#            `changed === metric` tell the cascade which upstream control
#            moved.
#
# Assigning to a property of a browser-side model (`lines.data = ...`,
# `status.text = ...`, `metric.options = ...`) redraws the affected widget or
# glyph immediately. No Python process is involved after page generation, so
# the same code works in a static HTML page and in a notebook output cell
# without re-running the cell.
#
# How state survives between calls
# --------------------------------
# Every invocation starts with fresh local variables, as a Python function
# call would. Anything that must persist (loaded records, the started/busy
# flags, the last settled selection, and the summary -> dash-slot
# assignments) is stored as an ad hoc attribute on the status model,
# `status._progress_state`. JavaScript objects accept new attributes freely,
# like instances of a plain Python class. The model is used instead of a
# module-level variable because Bokeh may compile this module more than once
# per page, and because several independent plots can share one page; each
# plot has its own status model.
#
# Why the busy flag and selection key exist
# -----------------------------------------
# `await fetch(...)` suspends this function and returns control to the
# browser until the response arrives, much like `await` in asyncio. Events
# that fire in the meantime, including change events caused by this
# function's own assignments to selector values, call the function again.
# Therefore the function claims startup and disables the controls before the
# first await, the busy flag rejects re-entrant updates, and the remembered
# selection key ignores callbacks that carry no real change (which would
# otherwise reset manual zoom or undo an intentional empty selection).
#
# High-level pseudocode (the helper functions precede the exported function):
#
#     get or create this plot's persistent state
#     if selection already handled or update in progress: return
#     mark update in progress
#     try:
#         on first invocation:
#             disable controls
#             load embedded records or await one external JSON fetch
#         cascade options: metric -> source -> label -> summary
#             derive each option list from records matching upstream choices
#             retain valid choices; fall back only at startup/upstream change
#             preserve an explicitly cleared control as an empty selection
#         enforce summary count cap and allocate stable dash slots
#             Mean requires solid; Median requires dashed
#         filter records by all selections and group into separate sequences
#             key = (metric, canonical label, summary, source)
#         sort each sequence by date and build fresh column-oriented data
#             lines: arrays per sequence, with NaN at explicit measurement gaps
#             points: finite measurements only, including original hover fields
#         replace line/point data; fit visible and Reset ranges to finite data
#         update title, informational legends, and count/gap/limit status
#     except error:
#         clear displayed data/legends, disable controls, show visible failure
#     finally:
#         remember the settled selection and release the busy flag
#
# Data layout: `records` is a list of row objects, one per summary record,
# with `date` as epoch milliseconds. A Bokeh ColumnDataSource instead needs an
# object of equally sized columns, so the function regroups rows into columns
# on every update. External JSON is fetched once per page load, not on each
# selection change; the user must reload the page to see a replaced file.
#
# Python validates embedded inputs; external JSON is assumed to use that same
# records contract. Handle fetch/parse failures here, not schema validation.
_PROGRESS_CALLBACK: str = r"""
// Null and empty labels share a logical identity, but original hover text stays
// untouched. JSON keys prevent real label text from colliding with a sentinel.
const canonical = value => value == null || value === "" ? "" : value;
const labelKey = value => JSON.stringify(canonical(value));
const sorted = values => [...new Set(values)].sort();

// Column layouts of the two data sources; a fresh copy is needed per update.
const emptyLines = () => ({xs: [], ys: [], color: [], width: [], alpha: [], dash: []});
const emptyPoints = () => ({date: [], summary_value: [], run_name: [], metric_name: [],
                            metric_info_label: [], summary_metric: [], color: []});

// SVG stroke-dasharray for each Bokeh named LineDash.
const dashArrays = {solid: "", dashed: "3 2", dotted: "2 1", dotdash: "2 4 6 4", dashdot: "6 4 2 4"};

// Labels and external URLs are data, never trusted HTML in status/legend markup.
const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);

export default async function(args, changed) {
    const {metric, source, label, summary, status, lines, points, plot, legends,
           records, url, colors, styles, dashes} = args;

    // Concurrent CustomJS compilation can yield multiple module instances.
    // The model survives all of them; claim initialization before any await.
    // State belongs to this plot's status model, not a page-global/module cache.
    const state = status._progress_state ??= {
        data: null, busy: false, started: false, slots: new Map(),
        previousSummaries: [], selection: null,
    };
    // Map summary name -> index into Bokeh's named dash list, retained across updates.
    const slots = state.slots;
    const selectionKey = () => JSON.stringify([metric.value, source.value, label.value, summary.value]);

    // Our setters also queue callbacks. Ignore duplicate selections so they do
    // not overwrite explicit user clearing or reset zoom between selections.
    if (state.started && selectionKey() === state.selection) return;
    if (state.busy) return;
    state.busy = true;
    try {
        // Claim startup before fetch yields control: concurrent callbacks cannot
        // issue a second request. Subsequent selections reuse the loaded records.
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

        // Cascade from upstream selections using unions of matching records.
        // Preserve surviving choices; only startup/upstream changes get fallback
        // selections. Clearing the control itself must remain an empty selection.
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

        // Labels do not use cascade(): option values are JSON identities with
        // separate display text, and no selection cap applies. Quoted display
        // text distinguishes a literal '(no label)' string from the null/empty
        // label presentation.
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

        // Reject only excess additions; a full selection can still be replaced.
        // Existing choices take priority over new ones when the user exceeds cap.
        let limited = false;
        if (summary.value.length > dashes.length) {
            const survivors = state.previousSummaries.filter(value => summary.value.includes(value));
            summary.value = [...survivors, ...summary.value.filter(value => !survivors.includes(value))]
                .slice(0, dashes.length);
            limited = true;
        }
        state.previousSummaries = [...summary.value];

        // Release deselected slots before allocating replacements. Preferred
        // summaries may displace an occupant, but all other survivors stay stable.
        for (const name of slots.keys()) if (!summary.value.includes(name)) slots.delete(name);
        // Preferred summaries take precedence over an existing occupant of their slot.
        for (const [name, dash] of [["Mean", "solid"], ["Median", "dashed"]]) {
            if (!summary.value.includes(name)) continue;
            const preferred = dashes.indexOf(dash);
            for (const [other, slot] of slots) {
                if (other !== name && slot === preferred) slots.delete(other);
            }
            slots.set(name, preferred);
        }
        for (const name of summary.value) {
            if (!slots.has(name)) {
                const used = new Set(slots.values());
                slots.set(name, dashes.findIndex((_, index) => !used.has(index)));
            }
        }
        rows = rows.filter(row => summary.value.includes(row.summary_metric));

        // Keep source and original-label sequences separate even with equal band
        // colors. JSON tuple keys avoid collisions from delimiters in real labels.
        const groups = new Map();
        for (const row of rows) {
            const key = JSON.stringify([canonical(row.metric_name), canonical(row.metric_info_label),
                                        canonical(row.summary_metric), row.visit_source]);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(row);
        }

        // multi_line columns contain one array/style per sequence; point columns
        // contain one scalar per finite measurement. NaN breaks a line at an
        // explicit gap without inventing missing dates or interpolated points.
        const lineData = emptyLines();
        const pointData = emptyPoints();
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

        // Replace whole sources together after building them, avoiding partial data
        // updates while selectors and their queued callbacks are being reconciled.
        lines.data = lineData;
        points.data = pointData;

        // Ranges use only finite measurements, not legend swatches or gap dates.
        // Pad ordinary spans and give empty/singleton selections usable ranges.
        const extent = (values, fallback, singleton) => {
            if (!values.length) return fallback;
            let low = Infinity, high = -Infinity;
            for (const value of values) {low = Math.min(low, value); high = Math.max(high, value);}
            const pad = low === high ? singleton(low) : (high - low) * 0.05;
            return [low - pad, high + pad];
        };
        for (const [range, bounds] of [
            [plot.x_range, extent(pointData.date, [0, 86400000], () => 86400000)],
            [plot.y_range, extent(pointData.summary_value, [0, 1],
                                 value => Math.max(Math.abs(value)*0.05, 1))]
        ]) {
            [range.start, range.end] = bounds;
            // Reset should fit this selection, not the document's initial records.
            [range.reset_start, range.reset_end] = bounds;
        }
        plot.title.text = metric.value || "Summary progress";

        // HTML/SVG legends are informational only: they cannot add synthetic data
        // to ranges or hide series independently of the selection controls.
        const swatch = (text, color, width = 2, alpha = 1, dash = "solid") =>
            `<span style="display:inline-block;margin-right:18px"><svg width="38" height="14">` +
            `<line x1="0" y1="7" x2="38" y2="7" stroke="${color}" stroke-width="${width}" ` +
            `opacity="${alpha}" stroke-dasharray="${dashArrays[dash] ?? ""}"/></svg> ${escape(text)}</span>`;
        legends[0].text = "<b>Source</b> " + sorted(rows.map(row => row.visit_source))
            .map(name => swatch(name, "black", ...styles[name])).join("");
        legends[1].text = "<b>Band</b> " + sorted(rows.map(row => row.band))
            .map(name => swatch(name, colors[name])).join("");
        legends[2].text = "<b>Summary</b> " + summary.value
            .map(name => swatch(name, "black", 2, 1, dashes[slots.get(name)])).join("");

        // Report successful loading separately from an empty or all-gap selection.
        // Keep cap/gap diagnostics visible rather than relying on browser console.
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
        // A failed load must not look like a successful plot of stale records.
        lines.data = emptyLines();
        points.data = emptyPoints();
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
    # Prepare the data source. ``records`` holds JSON-compatible rows with
    # epoch-ms dates, or None when the browser fetches ``url``; ``url`` is the
    # unchanged external URL, or None for embedded records. Share a browser
    # update path. Never read an external URL in Python or
    # embed a generation-time selector catalog that can become stale.
    if isinstance(summary_metrics, str):
        records, url = None, summary_metrics
    else:
        validate_summary_metrics(summary_metrics)

        # Report gaps, then normalize non-finite values to missing (JSON null).
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

    # Selector controls and status. Start empty: only loaded records determine
    # valid selector options.
    metric_select = bokeh.models.Select(title="Metric", options=[], value="", name="progress_metric")
    source_select = bokeh.models.MultiSelect(title="Source", options=[], value=[], name="progress_source")
    label_select = bokeh.models.MultiSelect(
        title="Metric info label", options=[], value=[], name="progress_label"
    )
    summary_select = bokeh.models.MultiSelect(
        title="Summary metric", options=[], value=[], name="progress_summary"
    )
    status = bokeh.models.Div(text="Loading summary metrics...", name="progress_status")

    # Data sources. One multi_line source fits a variable number of
    # sequences. Finite points
    # preserve isolated measurements and supply original hover data.
    line_source = bokeh.models.ColumnDataSource(
        dict(xs=[], ys=[], color=[], width=[], alpha=[], dash=[]), name="progress_lines"
    )
    point_source = bokeh.models.ColumnDataSource(
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

    # Figure and its renderers. Explicit ranges let selections update visible
    # and Reset bounds together.
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
    plot.multi_line(
        xs="xs",
        ys="ys",
        source=line_source,
        line_color="color",
        line_width="width",
        line_alpha="alpha",
        line_dash="dash",
    )
    scatter = plot.scatter(
        x="date",
        y="summary_value",
        source=point_source,
        color="color",
        size=8,
        alpha=0.6,
        hover_color="black",
        hover_alpha=1.0,
    )

    # Hover tool and axis formatting. Hover targets measurements, not
    # interpolated line positions.
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

    # Legend containers. Informational HTML legends never introduce reference
    # data.
    legends = [bokeh.models.Div(name=f"progress_{kind}_legend") for kind in ("source", "band", "summary")]
    band_cmap = make_band_cmap(bands=("u", "g", "r", "i", "z", "y", "all"))["transform"]
    colors = dict(zip(band_cmap.factors, band_cmap.palette))

    # Wire the browser callback. Explicit model/policy arguments keep separate
    # plots isolated.
    callback = bokeh.models.CustomJS(
        args=dict(
            metric=metric_select,
            source=source_select,
            label=label_select,
            summary=summary_select,
            status=status,
            lines=line_source,
            points=point_source,
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
    for control in (metric_select, source_select, label_select, summary_select):
        control.js_on_change("value", callback)

    # Start loading on document ready. Notebook embedding copies curdoc
    # callbacks into temporary documents.
    # A single generic dispatcher must discover only that output's models;
    # capturing each plot in document callback args would leak other outputs.
    status.tags.append(_PROGRESS_STARTUP)
    status.js_on_event(DocumentReady, callback)
    document = bokeh.io.curdoc()
    if not any(
        existing.name == _PROGRESS_STARTUP
        for existing in document.callbacks.js_event_callbacks.get(DocumentReady.event_name, [])
    ):
        document.js_on_event(
            DocumentReady, bokeh.models.CustomJS(name=_PROGRESS_STARTUP, code=_PROGRESS_DOCUMENT_READY)
        )
    return bokeh.layouts.column(
        bokeh.layouts.row(
            metric_select, source_select, label_select, summary_select, sizing_mode="stretch_width"
        ),
        status,
        plot,
        *legends,
        sizing_mode="stretch_width",
    )


# Older paired-plot API, retained for existing callers; it is unrelated to
# the interactive summary plot above.
SNAPSHOT_SCALAR_METRIC_FIGURE_NAME = "snapshot_scalar_metric_figure"
EXTRAPOLATED_SCALAR_METRIC_FIGURE_NAME = "extrapolated_scalar_metric_figure"


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
    # Keep the older computed-column API separate from summary records.
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

    # The reference ray belongs to the older API, not the summary plot.
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
