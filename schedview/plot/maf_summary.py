"""Interactive Bokeh plot for exploring MAF summary metrics."""

__all__ = ["make_metric_selector_plot", "save_metric_data_json"]

import json
import re
from datetime import datetime

import bokeh.core.enums
import bokeh.events
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.palettes
import bokeh.plotting
import numpy as np
import pandas as pd


def _build_data_dict(summary_df: pd.DataFrame) -> dict:
    """Build the metric data dictionary for JavaScript consumption.

    Groups summary_df by (metric_name, metric_info_label,
    summary_metric) and returns a dictionary mapping pipe-delimited
    keys to data arrays.

    Keys have the format "metric_name|info_label|summary_metric"
    where empty info labels are normalized to "<none>".

    Each value is a dict with keys:

    - "transition_date": list of float (ms since epoch)
    - "transition_date_labels": list of str ("YYYY-MM-DD")
    - "summary_value": list of float (may contain None for NaN)
    - "run_name": list of str
    """
    result = {}
    for label, group in summary_df.groupby(
        ["metric_name", "metric_info_label", "summary_metric"]
    ):
        # Create key from the three components
        metric_name = label[0]
        metric_info = label[1]
        summary_metric = label[2]

        # Normalize empty/NaN info_label to '<none>'
        if metric_info == "" or pd.isna(metric_info):
            info_display = "<none>"
        else:
            info_display = metric_info

        key = f"{metric_name}|{info_display}|{summary_metric}"

        # Convert date objects to timestamps (ms since epoch)
        timestamps = [
            datetime.combine(d, datetime.min.time()).timestamp()
            * 1000
            for d in group["transition_date"].values
        ]
        # ISO string labels for hover display
        date_labels = [
            d.strftime("%Y-%m-%d")
            for d in group["transition_date"].values
        ]

        # Convert summary_value to list
        # (NaN becomes float('nan'), handled by JSON encoder)
        summary_values = group["summary_value"].tolist()
        run_names = group["run_name"].tolist()

        result[key] = {
            "transition_date": timestamps,
            "transition_date_labels": date_labels,
            "summary_value": summary_values,
            "run_name": run_names,
        }

    return result


def _build_cascading_maps(
    unique_metrics: pd.DataFrame,
) -> tuple[dict, dict]:
    """Build cascading dropdown mappings.

    Returns
    -------
    metric_to_info : `dict`
        Maps metric_name -> sorted list of normalized info labels.
    metric_info_to_summary : `dict`
        Maps "metric_name|info_label" -> sorted list of summary
        metrics.
    """
    metric_to_info: dict[str, set[str]] = {}
    metric_info_to_summary: dict[str, set[str]] = {}

    for _, row in unique_metrics.iterrows():
        metric_name = row["metric_name"]
        metric_info_label = row["metric_info_label"]
        summary_metric = row["summary_metric"]

        # Normalize empty/NaN info_label to '<none>'
        if metric_info_label == "" or pd.isna(metric_info_label):
            normalized_info = "<none>"
        else:
            normalized_info = metric_info_label

        # Accumulate info labels per metric_name
        if metric_name not in metric_to_info:
            metric_to_info[metric_name] = set()
        metric_to_info[metric_name].add(normalized_info)

        # Accumulate summary metrics per "metric_name|info_label"
        key = f"{metric_name}|{normalized_info}"
        if key not in metric_info_to_summary:
            metric_info_to_summary[key] = set()
        metric_info_to_summary[key].add(summary_metric)

    # Sort sets into lists
    metric_to_info_sorted = {
        mn: sorted(info_labels)
        for mn, info_labels in metric_to_info.items()
    }
    metric_info_to_summary_sorted = {
        key: sorted(summary_metrics)
        for key, summary_metrics in metric_info_to_summary.items()
    }

    return metric_to_info_sorted, metric_info_to_summary_sorted


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_metric_data_json(
    summary_df: pd.DataFrame,
    unique_metrics: pd.DataFrame,
    json_path: str,
) -> None:
    """Save metric data and cascading dropdown mappings to JSON.

    The output file is loaded at runtime by the HTML visualization
    when ``data_json_url`` is set in ``make_metric_selector_plot``.

    Parameters
    ----------
    summary_df : `pandas.DataFrame`
        DataFrame from ``load_maf_summary`` with all metric values.
    unique_metrics : `pandas.DataFrame`
        DataFrame of unique metrics for building cascading mappings.
    json_path : `str`
        Path where the JSON file will be written.
    """
    data_dict = _build_data_dict(summary_df)
    metric_to_info, metric_info_to_summary = _build_cascading_maps(
        unique_metrics
    )

    output = {
        "data_dict": data_dict,
        "metric_to_info": metric_to_info,
        "metric_info_to_summary": metric_info_to_summary,
    }

    raw = json.dumps(output, cls=_NumpyEncoder)
    # json.dumps writes Python float('nan') as bare NaN, which is
    # invalid JSON.  Replace with null.
    raw = re.sub(r"\bNaN\b", "null", raw)
    with open(json_path, "w") as f:
        f.write(raw)


# ----------------------------------------------------------------
# Private helpers for make_metric_selector_plot
# ----------------------------------------------------------------


def _create_metric_selectors(
    metric_to_info: dict,
    metric_info_to_summary: dict,
) -> tuple:
    """Create the three selector widgets and initial selections.

    Returns
    -------
    metric_name_selector : `bokeh.models.Select`
    metric_info_selector : `bokeh.models.MultiSelect`
    summary_metric_selector : `bokeh.models.MultiSelect`
    initial_info_selection : `list` [`str`]
    initial_summary_selection : `list` [`str`]
    default_metric_name : `str`
    """
    metric_names = sorted(metric_to_info.keys())
    default_metric_name = metric_names[0]
    default_info_labels = metric_to_info[default_metric_name]
    initial_info_selection = default_info_labels[:2]

    # Get default summary metrics for the first info label
    first_info_label = initial_info_selection[0]
    summary_key = f"{default_metric_name}|{first_info_label}"
    default_summary_metrics = metric_info_to_summary.get(
        summary_key, []
    )
    initial_summary_selection = default_summary_metrics[:2]

    metric_name_selector = bokeh.models.Select(
        value=default_metric_name,
        options=metric_names,
        width=250,
    )

    metric_info_selector = bokeh.models.MultiSelect(
        value=initial_info_selection,
        options=default_info_labels,
        width=300,
        title="Metric Info Labels (select multiple to overplot):",
    )

    summary_metric_selector = bokeh.models.MultiSelect(
        value=initial_summary_selection,
        options=default_summary_metrics,
        width=300,
        title="Summary Metrics (select multiple to overplot):",
    )

    return (
        metric_name_selector,
        metric_info_selector,
        summary_metric_selector,
        initial_info_selection,
        initial_summary_selection,
        default_metric_name,
    )


def _preallocate_sources_and_renderers(
    p: bokeh.plotting.figure,
    line_colors: list[str],
    line_styles: list[str],
) -> list[list[bokeh.models.ColumnDataSource]]:
    """Pre-create ColumnDataSources and renderers for all slots.

    Creates a nested list ``sources[color_idx][linestyle_idx]``,
    each with scatter + line renderers attached to figure ``p``.

    Returns
    -------
    sources : `list` [`list` [`bokeh.models.ColumnDataSource`]]
        Nested list of data sources.
    """
    sources: list[list[bokeh.models.ColumnDataSource]] = []

    for color_idx in range(len(line_colors)):
        color_sources = []
        for linestyle_idx in range(len(line_styles)):
            source = bokeh.models.ColumnDataSource(
                data={
                    "transition_date": [],
                    "transition_date_labels": [],
                    "summary_value": [],
                    "run_name": [],
                    "info_label": [],
                    "summary_metric": [],
                }
            )

            p.scatter(
                x="transition_date",
                y="summary_value",
                source=source,
                size=8,
                color=line_colors[color_idx],
                alpha=0.6,
                line_dash=line_styles[linestyle_idx],
                hover_color="black",
                hover_alpha=1.0,
            )

            p.line(
                x="transition_date",
                y="summary_value",
                source=source,
                color=line_colors[color_idx],
                line_dash=line_styles[linestyle_idx],
                line_width=2,
            )

            color_sources.append(source)
        sources.append(color_sources)

    return sources


def _create_combined_legend(
    p: bokeh.plotting.figure,
    line_colors: list[str],
    line_styles: list[str],
    ticker_dates: list[float],
    initial_info_selection: list[str],
    initial_summary_selection: list[str],
) -> tuple:
    """Create the combined legend with reference renderers.

    Returns
    -------
    combined_legend : `bokeh.models.Legend`
    all_info_label_renderers : `list`
    all_summary_metric_renderers : `list`
    """
    # Reference renderers for info labels (color-coded)
    all_info_label_renderers = []
    for color_idx in range(len(line_colors)):
        ref_source = bokeh.models.ColumnDataSource(
            data={
                "x": [ticker_dates[0] if ticker_dates else 0],
                "y": [0],
            }
        )
        renderer = p.scatter(
            x="x",
            y="y",
            source=ref_source,
            size=8,
            color=line_colors[color_idx],
            alpha=0.6,
        )
        all_info_label_renderers.append(renderer)

    # Reference renderers for summary metrics (line-style in black)
    all_summary_metric_renderers = []
    for linestyle_idx in range(len(line_styles)):
        ref_source = bokeh.models.ColumnDataSource(
            data={
                "x": [ticker_dates[0] if ticker_dates else 0],
                "y": [0],
            }
        )
        renderer = p.line(
            x="x",
            y="y",
            source=ref_source,
            color="black",
            line_dash=line_styles[linestyle_idx],
            line_width=2,
        )
        all_summary_metric_renderers.append(renderer)

    # Build legend items
    combined_legend_items = []
    num_info_to_show = min(
        len(initial_info_selection), len(line_colors)
    )
    num_summary_to_show = min(
        len(initial_summary_selection), len(line_styles)
    )

    # Info label entries (color-coded)
    for color_idx in range(len(line_colors)):
        if color_idx < num_info_to_show:
            label = initial_info_selection[color_idx]
            visible = True
        else:
            label = f"Info {color_idx}"
            visible = False
        legend_item = bokeh.models.LegendItem(
            label=label,
            renderers=[all_info_label_renderers[color_idx]],
            visible=visible,
        )
        combined_legend_items.append(legend_item)

    # Summary metric entries (line style-coded)
    for linestyle_idx in range(len(line_styles)):
        if linestyle_idx < num_summary_to_show:
            label = initial_summary_selection[linestyle_idx]
            visible = True
        else:
            label = f"Summary {linestyle_idx}"
            visible = False
        legend_item = bokeh.models.LegendItem(
            label=label,
            renderers=[all_summary_metric_renderers[linestyle_idx]],
            visible=visible,
        )
        combined_legend_items.append(legend_item)

    combined_legend = bokeh.models.Legend(
        items=combined_legend_items,
        title="Legend",
        title_text_color="black",
        label_height=20,
        label_width=150,
        click_policy="hide",
        orientation="horizontal",
        ncols=7,
    )
    p.add_layout(combined_legend, "below")

    return (
        combined_legend,
        all_info_label_renderers,
        all_summary_metric_renderers,
    )


# The JavaScript callback code for the metric selector plot.
#
# === JS/Python Contract ===
# Python args dict provides: selector_name, selector_info,
#   selector_summary, plot, sources (nested list
#   [color_idx][linestyle_idx] of ColumnDataSource), num_colors,
#   num_styles, data_dict (inline dict or null), data_json_url
#   (string or null), metric_to_info, metric_info_to_summary,
#   combinedLegend.
#
# Data keys use pipe-delimited format:
#   "metric_name|info_label|summary_metric"
# Empty info labels are normalized to "<none>" by Python
#   (_build_data_dict).
#
# Legend layout:
#   items[0..num_colors-1] = info labels (by color)
#   items[num_colors..num_colors+num_styles-1] = summary metrics
#     (by line style)
#
# External data is cached in window._chimera_data after first fetch.
_CALLBACK_CODE = """
    const changed = cb_obj;
    const metric_name = selector_name.value;
    const selectedSummaryMetrics = selector_summary.value;
    const selectedInfoLabels = selector_info.value;

    // If metric_name changed, update the cascading dropdowns
    if (changed === selector_name) {
        const newInfoOptions = metric_to_info[metric_name];
        if (newInfoOptions && newInfoOptions.length > 0) {
            selector_info.options = newInfoOptions;

            // Keep current selections if still valid, else reset
            let hasValidSelection = false;
            for (const sel of selectedInfoLabels) {
                if (newInfoOptions.includes(sel)) {
                    hasValidSelection = true;
                    break;
                }
            }
            if (!hasValidSelection) {
                selector_info.value = newInfoOptions.slice(
                    0, Math.min(2, newInfoOptions.length));
            }

            // Update summary metrics for the first info label
            const firstInfo = selector_info.value[0]
                || newInfoOptions[0];
            const summaryKey = metric_name + '|' + firstInfo;
            const newSummaryOptions =
                metric_info_to_summary[summaryKey];
            if (newSummaryOptions && newSummaryOptions.length > 0) {
                selector_summary.options = newSummaryOptions;

                const newSummarySel = [];
                for (const sm of selectedSummaryMetrics) {
                    if (newSummaryOptions.includes(sm)
                            && newSummarySel.length < 2) {
                        newSummarySel.push(sm);
                    }
                }
                if (newSummarySel.length === 0) {
                    newSummarySel.push(newSummaryOptions[0]);
                }
                selector_summary.value = newSummarySel;
            }
        }
    }

    // Update plot title
    plot.title.text = metric_name + ' | '
        + selector_summary.value.join(', ');

    function performUpdate(theDataDict) {
        const curInfoLabels = selector_info.value;
        const curSummaryMetrics = selector_summary.value;
        const numInfoLabels = curInfoLabels.length;
        const numSummaryMetrics = curSummaryMetrics.length;

        for (let cIdx = 0; cIdx < num_colors; cIdx++) {
            for (let lIdx = 0; lIdx < num_styles; lIdx++) {
                const source = sources[cIdx][lIdx];

                if (cIdx < numInfoLabels
                        && lIdx < numSummaryMetrics) {
                    const infoLbl = curInfoLabels[cIdx];
                    const sumMetric = curSummaryMetrics[lIdx];
                    const infoKey =
                        (infoLbl === '' || infoLbl === '<none>')
                        ? '<none>' : infoLbl;
                    const dataKey = metric_name + '|' + infoKey
                        + '|' + sumMetric;
                    const newData = theDataDict[dataKey];

                    if (newData) {
                        source.data = {
                            transition_date:
                                newData.transition_date,
                            transition_date_labels:
                                newData.transition_date_labels,
                            summary_value:
                                newData.summary_value,
                            run_name: newData.run_name,
                            info_label: Array(
                                newData.transition_date.length
                            ).fill(infoLbl),
                            summary_metric: Array(
                                newData.transition_date.length
                            ).fill(sumMetric),
                        };
                    } else {
                        source.data = {
                            transition_date: [],
                            transition_date_labels: [],
                            summary_value: [],
                            run_name: [],
                            info_label: [],
                            summary_metric: [],
                        };
                    }
                } else {
                    source.data = {
                        transition_date: [],
                        transition_date_labels: [],
                        summary_value: [],
                        run_name: [],
                        info_label: [],
                        summary_metric: [],
                    };
                }
                source.change.emit();
            }
        }

        // Update legend: first num_colors items = info labels,
        // next num_styles items = summary metrics
        for (let i = 0; i < num_colors; i++) {
            const item = combinedLegend.items[i];
            if (i < curInfoLabels.length) {
                item.label = curInfoLabels[i];
                item.visible = true;
            } else {
                item.visible = false;
            }
        }
        for (let i = 0; i < num_styles; i++) {
            const item = combinedLegend.items[num_colors + i];
            if (i < curSummaryMetrics.length) {
                item.label = curSummaryMetrics[i];
                item.visible = true;
            } else {
                item.visible = false;
            }
        }
    }

    // Dispatch: inline data, cached fetch, or fetch from URL
    if (data_dict !== null) {
        performUpdate(data_dict);
    } else if (window._chimera_data) {
        performUpdate(window._chimera_data);
    } else {
        fetch(data_json_url)
            .then(r => r.json())
            .then(json => {
                window._chimera_data = json.data_dict;
                performUpdate(window._chimera_data);
            })
            .catch(err => {
                console.error(
                    'Failed to load metric data:', err);
            });
    }
"""


def make_metric_selector_plot(
    summary_df: pd.DataFrame,
    unique_metrics: pd.DataFrame,
    build_date: str | None = None,
    line_colors: list[str] | None = None,
    line_styles: list[str] | None = None,
    data_json_url: str | None = None,
) -> bokeh.layouts.Column:
    """Create an interactive Bokeh plot with metric selector widgets.

    Parameters
    ----------
    summary_df : `pandas.DataFrame`
        DataFrame from ``load_maf_summary`` containing all metric
        values.
    unique_metrics : `pandas.DataFrame`
        DataFrame of unique metric labels for the selector dropdowns.
    build_date : `str` or ``None``, optional
        Build date string to show in a heading above the plot.
    line_colors : `list` [`str`] or ``None``, optional
        Color values for info label differentiation.  Defaults to
        ``bokeh.palettes.Colorblind8``.
    line_styles : `list` [`str`] or ``None``, optional
        Line dash names for summary metric differentiation.  Defaults
        to ``list(bokeh.core.enums.LineDash)``.
    data_json_url : `str` or ``None``, optional
        URL to external JSON data file.  When set, data is fetched at
        runtime via fetch().  When ``None``, data is embedded inline.

    Returns
    -------
    layout : `bokeh.layouts.Column`
        Complete Bokeh layout ready for display or saving.
    """
    # Set up palettes
    line_colors = line_colors or list(bokeh.palettes.Colorblind8)
    line_styles = line_styles or list(bokeh.core.enums.LineDash)

    # Build internal data structures
    data_dict = _build_data_dict(summary_df)
    metric_to_info, metric_info_to_summary = _build_cascading_maps(
        unique_metrics
    )

    # Compute ticker dates: sorted unique transition_date values,
    # converted directly to ms-since-epoch timestamps.
    transition_date_objects = sorted(
        summary_df["transition_date"].unique()
    )
    ticker_dates_iso = [
        d.strftime("%Y-%m-%d") for d in transition_date_objects
    ]
    ticker_dates = [
        datetime.combine(d, datetime.min.time()).timestamp() * 1000
        for d in transition_date_objects
    ]

    # Create selector widgets and determine initial selections
    (
        metric_name_selector,
        metric_info_selector,
        summary_metric_selector,
        initial_info_selection,
        initial_summary_selection,
        default_metric_name,
    ) = _create_metric_selectors(metric_to_info, metric_info_to_summary)

    # Create figure
    title_text = (
        f"{default_metric_name}"
        f" | {', '.join(initial_summary_selection)}"
    )
    p = bokeh.plotting.figure(
        width=800,
        height=400,
        sizing_mode="stretch_width",
        x_axis_type="datetime",
        x_axis_label="Transition Date",
        y_axis_label="Summary Value",
        title=title_text,
        tools="pan,wheel_zoom,box_zoom,reset,hover,crosshair",
    )

    # Set x-axis ticks
    p.xaxis.ticker = bokeh.models.FixedTicker(ticks=ticker_dates)
    p.xaxis.major_label_overrides = dict(
        zip(ticker_dates, ticker_dates_iso)
    )
    p.x_range = bokeh.models.Range1d(
        min(ticker_dates), max(ticker_dates)
    )

    # Pre-create sources and renderers
    sources = _preallocate_sources_and_renderers(
        p, line_colors, line_styles
    )

    # Populate initial data
    for info_idx, info_label in enumerate(initial_info_selection):
        for summary_idx, summary_metric in enumerate(
            initial_summary_selection
        ):
            source = sources[info_idx][summary_idx]

            # Normalize info_label for key lookup
            if info_label == "" or info_label == "<none>":
                info_key = "<none>"
            else:
                info_key = info_label

            data_key = (
                f"{default_metric_name}|{info_key}|{summary_metric}"
            )
            data = data_dict.get(data_key)
            if data:
                n = len(data["transition_date"])
                source.data = {
                    "transition_date": data["transition_date"],
                    "transition_date_labels": data[
                        "transition_date_labels"
                    ],
                    "summary_value": data["summary_value"],
                    "run_name": data["run_name"],
                    "info_label": [info_label] * n,
                    "summary_metric": [summary_metric] * n,
                }

    # Configure hover tool
    p.hover.tooltips = [
        ("Date", "@transition_date_labels"),
        ("Value", "@summary_value{0.000}"),
        ("Run", "@run_name"),
        ("Info", "@info_label"),
        ("Summary Metric", "@summary_metric"),
    ]

    # Create combined legend
    (
        combined_legend,
        all_info_label_renderers,
        all_summary_metric_renderers,
    ) = _create_combined_legend(
        p,
        line_colors,
        line_styles,
        ticker_dates,
        initial_info_selection,
        initial_summary_selection,
    )

    # Build CustomJS callback
    callback_args = {
        "selector_name": metric_name_selector,
        "selector_summary": summary_metric_selector,
        "selector_info": metric_info_selector,
        "plot": p,
        "sources": sources,
        "num_colors": len(line_colors),
        "num_styles": len(line_styles),
        "data_dict": data_dict if data_json_url is None else None,
        "data_json_url": data_json_url,
        "metric_to_info": metric_to_info,
        "metric_info_to_summary": metric_info_to_summary,
        "combinedLegend": combined_legend,
        "allInfoLabelRenderers": all_info_label_renderers,
        "allSummaryMetricRenderers": all_summary_metric_renderers,
    }

    callback = bokeh.models.CustomJS(
        args=callback_args, code=_CALLBACK_CODE
    )

    # Attach callbacks to all three selectors
    metric_name_selector.js_on_change("value", callback)
    summary_metric_selector.js_on_change("value", callback)
    metric_info_selector.js_on_change("value", callback)

    # Pre-fetch on DocumentReady (only when data_json_url is set)
    if data_json_url is not None:
        prefetch_cb = bokeh.models.CustomJS(
            args={"data_json_url": data_json_url},
            code="""
                fetch(data_json_url)
                    .then(r => r.json())
                    .then(json => {
                        window._chimera_data = json.data_dict;
                        console.log('Pre-fetched metric data');
                    })
                    .catch(err => {
                        console.error(
                            'Failed to pre-fetch metric data:',
                            err);
                    });
            """,
        )
        p.js_on_event(bokeh.events.DocumentReady, prefetch_cb)

    # Assemble layout
    layout_elements = []
    if build_date:
        heading = bokeh.models.PreText(
            text=(
                "Summary Metric Explorer"
                f" (built: {build_date})"
            ),
            sizing_mode="stretch_width",
            height=30,
        )
        layout_elements.append(heading)

    selectors_row = bokeh.layouts.row(
        metric_name_selector,
        metric_info_selector,
        summary_metric_selector,
        sizing_mode="stretch_width",
    )
    layout_elements.append(selectors_row)
    layout_elements.append(p)

    return bokeh.layouts.column(
        *layout_elements, sizing_mode="stretch_width"
    )
