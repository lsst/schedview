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

from schedview.collect.progress import SummaryMetrics, _validate_reference_sim_tag, validate_summary_metrics
from schedview.plot.colors import make_band_cmap

__all__ = ["SOURCE_STYLES", "make_metric_line_plots", "make_summary_progress_plot"]

SOURCE_STYLES: dict[str, tuple[int, float]] = {
    "consdb": (1, 1.0),
    "chimera": (3, 0.6),
    "baseline": (5, 0.3),
}
"""Default source -> (width, alpha); plots snapshot their reference tag."""

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
// ---------------------------------------------------------------------------
// JavaScript notes for Python readers
// ---------------------------------------------------------------------------
// * `const x = ...` declares a name that cannot be rebound (the object it
//   refers to can still be modified); `let x = ...` declares one that can.
// * `===` / `!==` are strict equality tests (no type conversion), the usual
//   equivalent of Python's `==` / `!=`. `x == null` (two equals signs) is a
//   deliberate idiom that is true when x is either `null` or `undefined`.
// * `value => expression` is an arrow function, like `lambda value: expression`.
// * Backtick strings, `like ${this}`, are template literals, like f-strings.
// * `[...items]` copies (spreads) an iterable into a new array, like
//   `[*items]`; `f(...items)` passes items as separate arguments, like `f(*items)`.
// * `a ?? b` evaluates to `a` unless `a` is null/undefined, in which case `b`.
// * A plain object `{key: value}` is used like a dict with string keys.
//   `Map` and `Set` are the closer analogues of `dict` and `set` (they keep
//   insertion order and accept non-string keys).
// * Array methods: `a.map(f)` ~ `[f(x) for x in a]`, `a.filter(f)` ~
//   `[x for x in a if f(x)]`, `a.includes(x)` ~ `x in a`, `a.slice(i, j)` ~
//   `a[i:j]`, `a.push(x)` ~ `a.append(x)`, `a.join(s)` ~ `s.join(a)`.

// ---------------------------------------------------------------------------
// Helper functions and constants (module level, shared by every call)
// ---------------------------------------------------------------------------

// Return "" for a null, undefined, or empty value, and the value otherwise.
// Null and empty labels share a logical identity, but original hover text stays
// untouched: this is used only for grouping and selector identity.
function canonical(value) {
    if (value == null || value === "") {
        return "";
    }
    return value;
}

// Convert a metric_info_label into the string used as its selector option value.
// JSON keys prevent real label text from colliding with a sentinel:
//   null or ""   -> '""'
//   "chimera_g"  -> '"chimera_g"'   (the result includes the double quotes)
function labelKey(value) {
    return JSON.stringify(canonical(value));
}

// Python equivalent: sorted(set(values)). The default JavaScript sort compares
// values as strings, which is appropriate for the names sorted here.
function sorted(values) {
    const unique = new Set(values);
    return [...unique].sort();
}

// Column layouts of the two Bokeh ColumnDataSources (dicts of equal-length
// lists). These are functions so that each call returns fresh, empty lists;
// a fresh copy is needed per update.
//
// Line source: one entry per plotted sequence (drawn by plot.multi_line).
//   xs, ys        one list of dates / one list of values per sequence
//   color         band color of each sequence
//   width, alpha  line width and opacity of each sequence (from visit_source)
//   dash          Bokeh named dash of each sequence (from summary_metric)
function emptyLines() {
    return {xs: [], ys: [], color: [], width: [], alpha: [], dash: []};
}

// Point source: one entry per finite measurement (drawn by plot.scatter and
// used by the hover tool). Every column except `color` is copied from a record.
function emptyPoints() {
    return {
        date: [],
        summary_value: [],
        run_name: [],
        metric_name: [],
        metric_info_label: [],
        summary_metric: [],
        color: [],
    };
}

// SVG stroke-dasharray for each Bokeh named LineDash, used so that the HTML
// summary-legend swatches match the plotted line styles.
const dashArrays = {
    solid: "",
    dashed: "3 2",
    dotted: "2 1",
    dotdash: "2 4 6 4",
    dashdot: "6 4 2 4",
};

// Escape text before inserting it into HTML markup, like Python's html.escape.
// Labels and external URLs are data, never trusted HTML in status/legend markup.
// The regular expression /[&<>"']/g matches every ("g" = global) occurrence of
// any of those five characters; each match is replaced by its HTML entity.
const htmlEntities = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
function escape(value) {
    const text = String(value);
    return text.replace(/[&<>"']/g, character => htmlEntities[character]);
}

// ---------------------------------------------------------------------------
// The callback itself
// ---------------------------------------------------------------------------
// `async` allows the function to use `await`, as in an asyncio coroutine.
export default async function(args, changed) {
    // Unpack the CustomJS args (Python: metric = args.metric; source = ...).
    //   metric            Select widget; value is one metric-name string
    //   source, label,    MultiSelect widgets; value is a list of selected
    //     summary           option values, options is the list of choices
    //   status            Div showing loading/count/limit/error messages
    //   lines, points     ColumnDataSources drawn by the figure
    //   plot              the Bokeh figure (its title and x/y ranges are updated)
    //   legends           three Divs: [source legend, band legend, summary legend]
    //   records           embedded list of record objects, or null
    //   url               external JSON URL string, or null
    //   colors            {band: color}
    //   styles            {visit_source: [line width, alpha]}
    //   dashes            list of Bokeh named dash styles; its length is the
    //                     maximum number of summaries that may be selected
    const {metric, source, label, summary, status, lines, points, plot, legends,
           records, url, colors, styles, dashes} = args;

    // Persistent state for this plot, stored as an attribute of its status model.
    // Concurrent CustomJS compilation can yield multiple module instances.
    // The model survives all of them; claim initialization before any await.
    // State belongs to this plot's status model, not a page-global/module cache.
    //   data               loaded records (list of objects); null until loaded
    //   busy               true while an update is running
    //   started            true once the first (startup) call has begun
    //   slots              Map: summary name -> index into `dashes`
    //   previousSummaries  summary selection after the last update
    //   selection          selectionKey() string after the last update
    //   bandMode, labelRows previous label mode and upstream rows for translation
    if (status._progress_state == null) {
        status._progress_state = {
            data: null,
            busy: false,
            started: false,
            slots: new Map(),
            previousSummaries: [],
            selection: null,
            bandMode: false,
            labelRows: [],
        };
    }
    const state = status._progress_state;

    // Map summary name -> index into Bokeh's named dash list, retained across updates.
    const slots = state.slots;

    // One string encoding all four current selections, so that two complete
    // selections can be compared with a single `===`.
    function selectionKey() {
        return JSON.stringify([metric.value, source.value, label.value, summary.value]);
    }

    // Our setters also queue callbacks. Ignore duplicate selections so they do
    // not overwrite explicit user clearing or reset zoom between selections.
    if (state.started && selectionKey() === state.selection) {
        return;
    }
    // Ignore calls that arrive while another update is still in progress.
    if (state.busy) {
        return;
    }
    state.busy = true;

    try {
        // -------------------------------------------------------------------
        // Step 1: load the records (first call only)
        // -------------------------------------------------------------------
        // Claim startup before fetch yields control: concurrent callbacks cannot
        // issue a second request. Subsequent selections reuse the loaded records.
        let initial = false;
        if (!state.started) {
            state.started = true;
            initial = true;
            for (const control of [metric, source, label, summary]) {
                control.disabled = true;
            }
            if (url !== null) {
                // External data: the browser fetches the JSON file.
                status.text = `Loading ${escape(url)}...`;
                const response = await fetch(url, {cache: "no-store"});
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                state.data = await response.json();
            } else {
                // Embedded data: Python placed the records in the page.
                state.data = records;
            }
        }
        // `data` is a list of record objects (one per summary record) with
        // fields such as metric_name, visit_source, metric_info_label,
        // summary_metric, band, run_name, summary_value (a number or null),
        // and date (epoch milliseconds).
        const data = state.data;
        if (data === null) {
            return;
        }

        // -------------------------------------------------------------------
        // Step 2: cascade selector options, metric -> source -> label -> summary
        // -------------------------------------------------------------------
        // Cascade from upstream selections using unions of matching records.
        // Preserve surviving choices; only startup/upstream changes get fallback
        // selections. Clearing the control itself must remain an empty selection.
        // After each control, `rows` is narrowed to the records that match all
        // selections made so far.

        // Metric (single selection): initially choose the first sorted name.
        const metrics = sorted(data.map(row => row.metric_name));
        metric.options = metrics;
        if (initial) {
            metric.value = metrics[0] ?? "";  // "" when there are no records
        }
        metric.disabled = metrics.length === 0;
        let rows = data.filter(row => row.metric_name === metric.value);

        // Update one MultiSelect control from its newly available `options`.
        //   upstreamChanged  true when this call was triggered by a control that
        //                    is earlier in the cascade; only then (or at
        //                    startup) is the selection reconciled
        //   cap              maximum number of values to select
        //                    (Infinity means no limit: slice(0, Infinity) keeps all)
        function cascade(control, options, upstreamChanged, cap = Infinity) {
            // Currently selected values that are still available.
            const valid = control.value.filter(value => options.includes(value));
            control.options = options;
            control.disabled = options.length === 0;
            if (initial || upstreamChanged) {
                if (valid.length > 0) {
                    control.value = valid.slice(0, cap);
                } else {
                    // No previous choice survived: select all options, up to the cap.
                    control.value = options.slice(0, cap);
                }
            }
        }

        // Source: chimera first when available, then other sources in sorted order.
        const sourceOptions = sorted(rows.map(row => row.visit_source));
        const chimeraIndex = sourceOptions.indexOf("chimera");
        if (chimeraIndex > 0) {
            sourceOptions.splice(chimeraIndex, 1);
            sourceOptions.unshift("chimera");
        }
        cascade(source, sourceOptions, changed === metric);
        rows = rows.filter(row => source.value.includes(row.visit_source));

        // Use bands only when every upstream label is an exact source/band label.
        // Original labels still identify separate series and supply hover text.
        const bandOrder = ["all", "u", "g", "r", "i", "z", "y"];
        function standardLabel(row) {
            return bandOrder.includes(row.band) &&
                row.metric_info_label === `${row.visit_source}_${row.band}`;
        }
        const bandMode = rows.length > 0 && rows.every(standardLabel);
        const labels = sorted(rows.map(row => labelKey(row.metric_info_label)));
        const labelOptions = bandMode ?
            bandOrder.filter(band => rows.some(row => row.band === band)) : labels;
        let previousLabels = label.value;
        if (bandMode !== state.bandMode) {
            // Translate surviving choices when the same control changes meaning.
            if (bandMode) {
                previousLabels = sorted(state.labelRows.filter(row => standardLabel(row) &&
                    label.value.includes(labelKey(row.metric_info_label))).map(row => row.band));
            } else {
                previousLabels = sorted(rows.filter(row => standardLabel(row) &&
                    label.value.includes(row.band)).map(row => labelKey(row.metric_info_label)));
            }
        }
        const validLabels = previousLabels.filter(value => labelOptions.includes(value));
        label.title = bandMode ? "Band" : "Metric info label";
        // Bokeh accepts each option as a [value, displayed text] pair.
        // Quoted labels distinguish literal '(no label)' text from null/empty.
        label.options = labelOptions.map(key => {
            if (bandMode) return [key, key];
            const isEmptyLabel = JSON.parse(key) === "";
            const displayText = isEmptyLabel ? "(no label)" : key;
            return [key, displayText];
        });
        label.disabled = labelOptions.length === 0;
        if (initial || changed === metric || changed === source) {
            if (validLabels.length > 0) {
                label.value = validLabels;
            } else {
                label.value = labelOptions;
            }
        }
        state.bandMode = bandMode;
        state.labelRows = rows;
        rows = rows.filter(row =>
            label.value.includes(bandMode ? row.band : labelKey(row.metric_info_label)));

        // Summary: any automatic selection is capped at the number of dash styles.
        const summaryOptions = sorted(rows.map(row => row.summary_metric));
        const summaryUpstreamChanged = changed === metric || changed === source || changed === label;
        cascade(summary, summaryOptions, summaryUpstreamChanged, dashes.length);

        // -------------------------------------------------------------------
        // Step 3: enforce the summary selection cap
        // -------------------------------------------------------------------
        // Reject only excess additions; a full selection can still be replaced.
        // Existing choices take priority over new ones when the user exceeds cap.
        let limited = false;
        if (summary.value.length > dashes.length) {
            // Summaries that were already selected before this change...
            const survivors = state.previousSummaries.filter(value => summary.value.includes(value));
            // ...followed by newly added ones, then truncated to the cap.
            const added = summary.value.filter(value => !survivors.includes(value));
            const prioritized = [...survivors, ...added];
            summary.value = prioritized.slice(0, dashes.length);
            limited = true;
        }
        state.previousSummaries = [...summary.value];

        // -------------------------------------------------------------------
        // Step 4: assign a dash-style slot to each selected summary
        // -------------------------------------------------------------------
        // Release deselected slots before allocating replacements. Preferred
        // summaries may displace an occupant, but all other survivors stay stable.
        // (Unlike a Python dict, a JavaScript Map may be modified while iterating.)
        for (const name of slots.keys()) {
            if (!summary.value.includes(name)) {
                slots.delete(name);
            }
        }
        // Preferred summaries take precedence over an existing occupant of their slot.
        const preferredDashes = [["Mean", "solid"], ["Median", "dashed"]];
        for (const [name, dash] of preferredDashes) {
            if (!summary.value.includes(name)) {
                continue;
            }
            const preferred = dashes.indexOf(dash);
            for (const [other, slot] of slots) {
                if (other !== name && slot === preferred) {
                    slots.delete(other);
                }
            }
            slots.set(name, preferred);
        }
        // Give each remaining selected summary the lowest unused slot index.
        // `findIndex` returns the index of the first element passing the test;
        // `_` is the conventional name for an unused argument (the element).
        for (const name of summary.value) {
            if (!slots.has(name)) {
                const used = new Set(slots.values());
                const firstFree = dashes.findIndex((_, index) => !used.has(index));
                slots.set(name, firstFree);
            }
        }
        rows = rows.filter(row => summary.value.includes(row.summary_metric));

        // -------------------------------------------------------------------
        // Step 5: group the selected records into separate line sequences
        // -------------------------------------------------------------------
        // Keep source and original-label sequences separate even with equal band
        // colors. JSON tuple keys avoid collisions from delimiters in real labels.
        // `groups` maps JSON string of [metric, label, summary, source] -> list
        // of records. Python analogue: groups = defaultdict(list)
        const groups = new Map();
        for (const row of rows) {
            const key = JSON.stringify([
                canonical(row.metric_name),
                canonical(row.metric_info_label),
                canonical(row.summary_metric),
                row.visit_source,
            ]);
            if (!groups.has(key)) {
                groups.set(key, []);
            }
            groups.get(key).push(row);
        }

        // -------------------------------------------------------------------
        // Step 6: build new column data for the line and point sources
        // -------------------------------------------------------------------
        // multi_line columns contain one array/style per sequence; point columns
        // contain one scalar per finite measurement. NaN breaks a line at an
        // explicit gap without inventing missing dates or interpolated points.
        const lineData = emptyLines();
        const pointData = emptyPoints();

        // True when a record has a real, finite measurement (not null, NaN, or ±Infinity).
        function finite(row) {
            return row.summary_value !== null && Number.isFinite(row.summary_value);
        }

        for (const group of groups.values()) {
            // Sort this sequence by date, in place. The comparison function gives
            // numeric order (the default sort would compare numbers as strings).
            group.sort((a, b) => a.date - b.date);

            // All records in a group share source, band, and summary, so the
            // first record determines the style of the whole line.
            const first = group[0];
            const color = colors[first.band];
            const [width, alpha] = styles[first.visit_source];
            const dash = dashes[slots.get(first.summary_metric)];

            const xs = group.map(row => row.date);
            const ys = group.map(row => finite(row) ? row.summary_value : NaN);

            lineData.xs.push(xs);
            lineData.ys.push(ys);
            lineData.color.push(color);
            lineData.width.push(width);
            lineData.alpha.push(alpha);
            lineData.dash.push(dash);

            // Add one point per finite measurement, copying each point column
            // from the record, except `color`, which comes from the band.
            for (const row of group.filter(finite)) {
                for (const field of Object.keys(pointData)) {
                    if (field === "color") {
                        pointData[field].push(color);
                    } else {
                        pointData[field].push(row[field]);
                    }
                }
            }
        }

        // Replace whole sources together after building them, avoiding partial data
        // updates while selectors and their queued callbacks are being reconciled.
        lines.data = lineData;
        points.data = pointData;

        // -------------------------------------------------------------------
        // Step 7: fit the axis ranges to the selected finite data
        // -------------------------------------------------------------------
        // Ranges use only finite measurements, not legend swatches or gap dates.
        // Pad ordinary spans and give empty/singleton selections usable ranges.
        //   values     numbers to fit
        //   fallback   [start, end] used when there are no values
        //   singleton  function(value) -> padding used when all values are equal
        // Returns [start, end].
        function extent(values, fallback, singleton) {
            if (values.length === 0) {
                return fallback;
            }
            let low = Infinity;
            let high = -Infinity;
            for (const value of values) {
                low = Math.min(low, value);
                high = Math.max(high, value);
            }
            let pad;
            if (low === high) {
                pad = singleton(low);
            } else {
                pad = (high - low) * 0.05;
            }
            return [low - pad, high + pad];
        }

        const oneDayMs = 86400000;  // dates are epoch milliseconds
        const xBounds = extent(pointData.date, [0, oneDayMs], () => oneDayMs);
        const yBounds = extent(pointData.summary_value, [0, 1],
                               value => Math.max(Math.abs(value) * 0.05, 1));
        const rangesAndBounds = [
            [plot.x_range, xBounds],
            [plot.y_range, yBounds],
        ];
        for (const [range, bounds] of rangesAndBounds) {
            const [start, end] = bounds;
            range.start = start;
            range.end = end;
            // Reset should fit this selection, not the document's initial records.
            range.reset_start = start;
            range.reset_end = end;
        }
        // `||` falls back when metric.value is "" (like Python's `or`).
        plot.title.text = metric.value || "Summary progress";

        // -------------------------------------------------------------------
        // Step 8: rebuild the three HTML legends
        // -------------------------------------------------------------------
        // HTML/SVG legends are informational only: they cannot add synthetic data
        // to ranges or hide series independently of the selection controls.

        // Return HTML for one legend entry: a short SVG line sample and its text.
        function swatch(text, color, width = 2, alpha = 1, dash = "solid") {
            const dashArray = dashArrays[dash] ?? "";
            return `<span style="display:inline-block;margin-right:18px"><svg width="38" height="14">` +
                `<line x1="0" y1="7" x2="38" y2="7" stroke="${color}" stroke-width="${width}" ` +
                `opacity="${alpha}" stroke-dasharray="${dashArray}"/></svg> ${escape(text)}</span>`;
        }

        // Source legend: black lines with each source's width and alpha.
        // `...styles[name]` passes [width, alpha] as two separate arguments.
        const shownSources = sorted(rows.map(row => row.visit_source));
        const sourceSwatches = shownSources.map(name => swatch(name, "black", ...styles[name]));
        legends[0].text = "<b>Source</b> " + sourceSwatches.join("");

        // Band legend: default-width lines in each band's color.
        const shownBands = sorted(rows.map(row => row.band));
        const bandSwatches = shownBands.map(name => swatch(name, colors[name]));
        legends[1].text = "<b>Band</b> " + bandSwatches.join("");

        // Summary legend: black lines in each selected summary's dash style.
        const summarySwatches = summary.value.map(
            name => swatch(name, "black", 2, 1, dashes[slots.get(name)]));
        legends[2].text = "<b>Summary</b> " + summarySwatches.join("");

        // -------------------------------------------------------------------
        // Step 9: status message
        // -------------------------------------------------------------------
        // Report successful loading separately from an empty or all-gap selection.
        // Keep cap/gap diagnostics visible rather than relying on browser console.
        const pointCount = pointData.date.length;
        const noData = pointCount === 0;
        const limitText = `Select at most ${dashes.length} summaries; deselect one to replace it.`;
        let countText;
        if (noData) {
            countText = "No finite data for the current selection.";
        } else {
            countText = `${pointCount} finite measurements.`;
        }
        const gaps = rows.filter(row => !finite(row)).length;

        let message = "";
        if (limited) {
            // The user just tried to select more than the cap.
            message += `Selection limit: ${limitText} `;
        }
        message += countText;
        if (gaps > 0) {
            message += ` ${gaps} missing/non-finite measurements shown as gaps.`;
        }
        if (summary.options.length > dashes.length && !limited) {
            // More summaries exist than can be shown at once: explain the cap.
            message += ` ${limitText}`;
        }
        if (url !== null) {
            message += ` Source: ${escape(url)}`;
        }
        status.text = message;
    } catch (error) {
        // A failed load must not look like a successful plot of stale records.
        lines.data = emptyLines();
        points.data = emptyPoints();
        for (const legend of legends) {
            legend.text = "";
        }
        const dataSource = url ?? "embedded records";
        status.text = `Failed to load ${escape(dataSource)}: ${escape(error.message)}`;
        for (const control of [metric, source, label, summary]) {
            control.disabled = true;
        }
    } finally {
        // CustomJS.execute awaits compilation even for cached modules. Ignore
        // queued callbacks from our own setters after this update has settled.
        state.selection = selectionKey();
        state.busy = false;
    }
}
"""


def make_summary_progress_plot(
    summary_metrics: SummaryMetrics | str, *, reference_sim_tag: str = "baseline"
) -> bokeh.models.UIElement:
    """Create a standalone interactive plot of scalar MAF summary records.

    Parameters
    ----------
    summary_metrics : pandas.DataFrame or str
        Validated summary records, including filtered copies, or a JSON URL.
        URLs are fetched once on page load and resolved against the page URL.
        External pages must be HTTP(S)-served with same-origin or CORS access.
    reference_sim_tag : str, optional
        One literal, case-sensitive reference prefix, default ``"baseline"``.
        An alternate replaces baseline. Pass the same tag to collection and
        external JSON export. Each plot snapshots its own reference style.
        Empty/non-string and reserved consdb/chimera tags raise ``ValueError``.

    Returns
    -------
    bokeh.models.UIElement
        Four cascading selectors, status, figure, and three informational
        legends. Embedded records require no companion data file or server.
        The label selector becomes a band selector when all labels matching
        the selected metric and sources are exact source/band labels.
    """
    _validate_reference_sim_tag(reference_sim_tag)
    styles = {
        "consdb": SOURCE_STYLES["consdb"],
        "chimera": SOURCE_STYLES["chimera"],
        reference_sim_tag: SOURCE_STYLES["baseline"],
    }
    # Prepare the data source. ``records`` holds JSON-compatible rows with
    # epoch-ms dates, or None when the browser fetches ``url``; ``url`` is the
    # unchanged external URL, or None for embedded records. Share a browser
    # update path. Never read an external URL in Python or
    # embed a generation-time selector catalog that can become stale.
    if isinstance(summary_metrics, str):
        records, url = None, summary_metrics
    else:
        validate_summary_metrics(summary_metrics, reference_sim_tag=reference_sim_tag)

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
            styles=styles,
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
