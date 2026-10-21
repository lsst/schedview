from collections.abc import Mapping
from types import MappingProxyType

import json
import os
import re as re_module

import bokeh.core.enums
import bokeh.events
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.palettes
import bokeh.plotting
import click
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

__all__ = [
    "make_metric_line_plots",
    "make_metric_selector_plot",
]


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
    """Create Bokeh line and scatter plots for a scalar metric.

    Parameters
    ----------
    metric_name : str
        Used in the titles of the generated figures.
    metric_values : pd.DataFrame
        DataFrame containing a datetime column named ``date`` and metric
        columns ``baseline``, ``snapshot`` and ``chimera``. The index is
        expected to be a ``pd.DatetimeIndex``.
    snapshot_line_kwargs : `Mapping`
        Keyword args passed to ``bokeh.figure.line`` for the snapshot plot.
    snapshot_scatter_kwargs : `Mapping`
        Keyword args passed to ``bokeh.figure.scatter`` for the snapshot plot.
    baseline_line_kwargs : `Mapping`
        Keyword args passed to ``bokeh.figure.line`` for the baseline line.
    baseline_ray_kwargs : `Mapping`
        Keyword args passod to ``bokeh.figure.ray`` for the baseline
        extrpolated metric value.
    chimera_line_kwargs : `Mapping`
        Keyword args passed to ``bokeh.figure.line`` for the chimera metric.
    chimera_scatter_kwargs : `Mapping`
        Keyword args passed to ``bokeh.figure.scatter`` for the chimera metric.


    Returns
    -------
    showable : `bokeh.layouts.Row`
        A Bokeh layout row containing the two figures.
    """

    metric_values_ds = bokeh.models.ColumnDataSource(metric_values)

    # Build the left plot showing instantaneous metric values.
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

    # Build the right plot showing the metric values extrapolated to the
    # target date.
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

def make_metric_selector_plot(
    summary_df: pd.DataFrame,
    unique_metrics: pd.DataFrame,
    build_date: str | None = None,
    line_colors: list[str] | None = None,
    line_styles: list[str] | None = None,
    data_json_url: str | None = None,
) -> "bokeh.layouts.Column":
    """Create an interactive Bokeh plot with metric selector.

    Uses a dropdown for metric_name, MultiSelect widgets for summary_metric and
    metric_info_label. Multiple info labels can be selected and overplotted with
    different colors. Multiple summary metrics can be selected and overplotted with
    different linestyles. Legends outside the plot show the color and line style mappings.

    The function pre-creates sources with unique (color, linestyle) combinations.
    The number of sources is determined by len(line_colors) * len(line_styles).
    When the user makes selections, each selected info_label is assigned a color
    and each selected summary_metric is assigned a line style. Data is then assigned
    to sources whose (color, linestyle) combination matches the selected items.

    When data_json_url is None (default), all metric data is embedded inline.
    When set, the JavaScript callback fetches data from the external JSON file
    at runtime. A DocumentReady callback pre-fetches the data so it is cached
    before the user interacts with the selectors.

    Parameters
    ----------
    summary_df : pd.DataFrame
        DataFrame from load_chimera_summary containing all metric values.
    unique_metrics : pd.DataFrame
        DataFrame of unique metric labels for the selector dropdowns.
    build_date : str | None
        Optional build date string to show in a top-level heading.
    line_colors : list[str] | None
        Optional list of color values (hex strings or named colors). If None,
        uses bokeh.palettes.Colorblind8 (8 colors).
    line_styles : list[str] | None
        Optional list of line style names (e.g., 'solid', 'dashed', 'dotted').
        If None, uses bokeh.core.enums.LineDash values.
    data_json_url : str | None
        Optional URL to external JSON data file. When set, metric data is
        fetched at runtime instead of embedded inline.

    Returns
    -------
    "bokeh.layouts.Column"
        Bokeh layout with Select widgets, MultiSelect widgets, plot, and legends.
    """
    # Set up color and style palettes
    line_colors = line_colors if line_colors is not None else list(bokeh.palettes.Colorblind8)
    line_styles = line_styles if line_styles is not None else list(bokeh.core.enums.LineDash)

    # Total number of sources to pre-allocate
    max_sources = len(line_styles) * len(line_colors)
    # Get unique transition dates (sorted)
    transition_date_objects = sorted(summary_df['transition_date'].unique())

    # Convert transition dates to ISO format for Bokeh (required for datetime x-axis)
    transition_dates_iso = [d.strftime('%Y-%m-%d') for d in transition_date_objects]

    # Build cascading dropdown mappings:
    # metric_name -> list of valid metric_info_labels
    # (metric_name, metric_info_label) -> list of valid summary_metrics
    metric_to_info = {}
    metric_info_to_summary = {}

    for _, row in unique_metrics.iterrows():
        mn = row['metric_name']
        mili = row['metric_info_label']
        sm = row['summary_metric']

        if mn not in metric_to_info:
            metric_to_info[mn] = set()
        metric_to_info[mn].add(mili)

        key = (mn, mili)
        if key not in metric_info_to_summary:
            metric_info_to_summary[key] = set()
        metric_info_to_summary[key].add(sm)

    # Handle empty metric_info_label case - show "<none>" instead of empty string
    def normalize_info_label(ml):
        return '<none>' if ml == '' or pd.isna(ml) else ml

    def denormalize_info_label(ml):
        return '' if ml == '<none>' else ml

    # Get unique values for each dropdown level
    metric_names = sorted(metric_to_info.keys())

    # Get first valid combination for defaults
    first_row = unique_metrics.iloc[0]
    default_metric_name = first_row['metric_name']
    default_info_label = normalize_info_label(first_row['metric_info_label'])
    default_summary_metric = first_row['summary_metric']

    # Get valid info labels for default metric_name
    default_info_labels = sorted([normalize_info_label(ml) for ml in metric_to_info[default_metric_name]])

    # Get valid summary metrics for default (metric_name, metric_info_label)
    default_summary_metrics = sorted(metric_info_to_summary[(default_metric_name, denormalize_info_label(default_info_label))])

    # Create metric name dropdown
    metric_name_selector = bokeh.models.Select(
        value=default_metric_name,
        options=metric_names,
        width=250,
    )

    # Create summary metric MultiSelect (allows multiple selections)
    # Initial selection: first two summary metrics if available, otherwise just first
    initial_summary_selection = default_summary_metrics[:2] if len(default_summary_metrics) > 1 else default_summary_metrics[:1]

    summary_metric_selector = bokeh.models.MultiSelect(
        value=initial_summary_selection,
        options=default_summary_metrics,
        width=300,
        title='Summary Metrics (select multiple to overplot):',
    )

    # Create metric info label MultiSelect (allows multiple selections)
    # Initial selection: first two info labels if available, otherwise just first
    initial_info_selection = default_info_labels[:2] if len(default_info_labels) > 1 else default_info_labels[:1]

    metric_info_selector = bokeh.models.MultiSelect(
        value=initial_info_selection,
        options=default_info_labels,
        width=300,
        title='Metric Info Labels (select multiple to overplot):',
    )

    # Get title for initial plot (use initial summary selection for title)
    title = f"{default_metric_name} | {', '.join(initial_summary_selection)}"

    # Create the plot with datetime x-axis
    p = bokeh.plotting.figure(
        width=800,
        height=400,
        sizing_mode='stretch_width',
        x_axis_type='datetime',
        x_axis_label='Transition Date',
        y_axis_label='Summary Value',
        title=title,
        tools='pan,wheel_zoom,box_zoom,reset,hover,crosshair',
    )

    # Convert dates to timestamps (milliseconds since epoch) for Bokeh datetime axis
    def date_to_timestamps(date_series):
        return [datetime.combine(d, datetime.min.time()).timestamp() * 1000 for d in date_series]

    # Pre-create sources with unique (color, linestyle) combinations
    # Create a nested list: sources[color_idx][linestyle_idx]
    sources = []  # sources[color_idx][linestyle_idx] -> ColumnDataSource

    for color_idx in range(len(line_colors)):
        color_sources = []
        for linestyle_idx in range(len(line_styles)):
            source = bokeh.models.ColumnDataSource(data={
                'transition_date': [],
                'transition_date_labels': [],
                'summary_value': [],
                'run_name': [],
                'info_label': [],
                'summary_metric': [],
            })

            # Add scatter points with this (color, linestyle)
            scatter = p.scatter(
                x='transition_date',
                y='summary_value',
                source=source,
                size=8,
                color=line_colors[color_idx],
                alpha=0.6,
                line_dash=line_styles[linestyle_idx],
                hover_color='black',
                hover_alpha=1.0,
                name=f'scatter_{linestyle_idx}_{color_idx}',
            )

            # Add line connecting points with this linestyle
            line = p.line(
                x='transition_date',
                y='summary_value',
                source=source,
                color=line_colors[color_idx],
                line_dash=line_styles[linestyle_idx],
                line_width=2,
                name=f'line_{linestyle_idx}_{color_idx}',
            )

            color_sources.append(source)
        sources.append(color_sources)

    # Populate initial data for the default metric and initial selections
    # Map each (info_label, summary_metric) combination to the correct source
    # This creates a 1:1 mapping: sources[info_idx][summary_idx] displays the data
    # for (info_label, summary_metric) at selections[info_idx] and [summary_idx]
    for info_idx, info_label in enumerate(initial_info_selection):
        color_idx = info_idx
        for summary_idx, summary_metric in enumerate(initial_summary_selection):
            linestyle_idx = summary_idx
            source = sources[color_idx][linestyle_idx]

            # Get data for this (info_label, summary_metric) combination
            data = get_all_metric_data_dict(summary_df).get(
                f"{default_metric_name}|{info_label}|{summary_metric}"
            )
            if data:
                source.data = data

    # Extract sources from renderers for JavaScript access
    # sources is already a nested list: sources[color_idx][linestyle_idx]
    render_sources = sources

    # Configure hover tool
    p.hover.tooltips = [
        ('Date', '@transition_date_labels'),
        ('Value', '@summary_value{0.000}'),
        ('Run', '@run_name'),
        ('Info', '@info_label'),
        ('Summary Metric', '@summary_metric'),
    ]

    # Use FixedTicker for the specific dates
    # Convert dates to timestamps for the ticker
    ticker_dates = [datetime.strptime(d, '%Y-%m-%d').timestamp() * 1000 for d in transition_dates_iso]
    p.xaxis.ticker = bokeh.models.FixedTicker(ticks=ticker_dates)
    p.xaxis.major_label_overrides = dict(zip(ticker_dates, transition_dates_iso))

    # Set explicit x_range to prevent "could not set initial ranges" error
    p.x_range = bokeh.models.Range1d(min(ticker_dates), max(ticker_dates))

    # Build cascading dropdown data for JavaScript
    metric_to_info_json = {
        mn: [normalize_info_label(ml) for ml in sorted(info_labels)]
        for mn, info_labels in metric_to_info.items()
    }
    metric_info_to_summary_json = {
        f"{mn}|{normalize_info_label(ml)}": sorted(summary_metrics)
        for (mn, ml), summary_metrics in metric_info_to_summary.items()
    }

    # Pre-create legend items for all possible colors and linestyles
    # This allows us to toggle visibility instead of recreating items in JavaScript
    # Create invisible reference renderers for all possible legend items
    all_info_label_renderers = []
    for color_idx in range(len(line_colors)):
        ref_source = bokeh.models.ColumnDataSource(data={
            'x': [ticker_dates[0] if ticker_dates else 0],
            'y': [0],
        })
        renderer = p.scatter(
            x='x',
            y='y',
            source=ref_source,
            size=8,
            color=line_colors[color_idx],
            alpha=0.6,
            name=f'legend_info_{color_idx}',
        )
        all_info_label_renderers.append(renderer)

    all_summary_metric_renderers = []
    for linestyle_idx in range(len(line_styles)):
        ref_source2 = bokeh.models.ColumnDataSource(data={
            'x': [ticker_dates[0] if ticker_dates else 0],
            'y': [0],
        })
        renderer = p.line(
            x='x',
            y='y',
            source=ref_source2,
            color='black',
            line_dash=line_styles[linestyle_idx],
            line_width=2,
            name=f'legend_summary_{linestyle_idx}',
        )
        all_summary_metric_renderers.append(renderer)

    # Create combined legend with all possible items
    # Initialize with correct labels and visibility based on initial selection
    combined_legend_items = []
    num_info_to_show = min(len(initial_info_selection), len(line_colors))
    num_summary_to_show = min(len(initial_summary_selection), len(line_styles))

    # Add info label entries (color-coded)
    for color_idx in range(len(line_colors)):
        label = initial_info_selection[color_idx] if color_idx < num_info_to_show else f'Info Label {color_idx}'
        visible = color_idx < num_info_to_show
        legend_item = bokeh.models.LegendItem(
            label=label,
            renderers=[all_info_label_renderers[color_idx]],
            visible=visible
        )
        combined_legend_items.append(legend_item)

    # Add summary metric entries (line style-coded)
    for linestyle_idx in range(len(line_styles)):
        label = initial_summary_selection[linestyle_idx] if linestyle_idx < num_summary_to_show else f'Summary Metric {linestyle_idx}'
        visible = linestyle_idx < num_summary_to_show
        legend_item = bokeh.models.LegendItem(
            label=label,
            renderers=[all_summary_metric_renderers[linestyle_idx]],
            visible=visible
        )
        combined_legend_items.append(legend_item)

    combined_legend = bokeh.models.Legend(
        items=combined_legend_items,
        title='Legend',
        title_text_color='black',
        label_height=20,
        label_width=150,
        click_policy='hide',
        orientation='horizontal',
        ncols=7,
    )
    p.add_layout(combined_legend, "below")

    # Build JavaScript callback with references to legends
    # When data_json_url is set, data is fetched at runtime instead of embedded inline
    callback_data_dict = None if data_json_url is not None else get_all_metric_data_dict(summary_df)
    callback_data_json_url = data_json_url

    callback_container = bokeh.models.CustomJS(args={
        'selector_name': metric_name_selector,
        'selector_summary': summary_metric_selector,
        'selector_info': metric_info_selector,
        'plot': p,
        'sources': render_sources,
        'num_colors': len(line_colors),
        'num_styles': len(line_styles),
        'data_dict': callback_data_dict,
        'data_json_url': callback_data_json_url,
        'ticker_dates': ticker_dates,
        'transition_dates_iso': transition_dates_iso,
        'metric_to_info': metric_to_info_json,
        'metric_info_to_summary': metric_info_to_summary_json,
        'line_styles': line_styles,
        'line_colors': line_colors,
        'combinedLegend': combined_legend,
        'allInfoLabelRenderers': all_info_label_renderers,
        'allSummaryMetricRenderers': all_summary_metric_renderers,
    }, code='''
    const changed = cb_obj;
    const metric_name = selector_name.value;
    const selectedSummaryMetrics = selector_summary.value;
    const selectedInfoLabels = selector_info.value;

    // If metric_name changed, update the cascading dropdowns
    if (changed === selector_name) {
        const newInfoOptions = metric_to_info[metric_name];
        if (newInfoOptions && newInfoOptions.length > 0) {
            selector_info.options = newInfoOptions;

            let hasValidSelection = false;
            for (const sel of selectedInfoLabels) {
                if (newInfoOptions.includes(sel)) {
                    hasValidSelection = true;
                    break;
                }
            }
            if (!hasValidSelection) {
                selector_info.value = newInfoOptions.slice(0, Math.min(2, newInfoOptions.length));
            }

            const firstInfoLabel = newInfoOptions[0];
            const summaryKey = metric_name + '|' + firstInfoLabel;
            const newSummaryOptions = metric_info_to_summary[summaryKey];
            if (newSummaryOptions && newSummaryOptions.length > 0) {
                selector_summary.options = newSummaryOptions;

                const newSummarySelection = [];
                for (const sm of selectedSummaryMetrics) {
                    if (newSummaryOptions.includes(sm) && newSummarySelection.length < 2) {
                        newSummarySelection.push(sm);
                    }
                }
                if (newSummarySelection.length === 0) {
                    newSummarySelection.push(newSummaryOptions[0]);
                }
                selector_summary.value = newSummarySelection;
            }
        }
    }

    plot.title.text = metric_name + ' | ' + selectedSummaryMetrics.join(', ');

    function performUpdate(theDataDict) {
        let updatedCount = 0;
        const numInfoLabels = selectedInfoLabels.length;
        const numSummaryMetrics = selectedSummaryMetrics.length;

        for (let colorIdx = 0; colorIdx < num_colors; colorIdx++) {
            for (let linestyleIdx = 0; linestyleIdx < num_styles; linestyleIdx++) {
                const source = sources[colorIdx][linestyleIdx];

                if (colorIdx < numInfoLabels && linestyleIdx < numSummaryMetrics) {
                    const assignedInfoLabel = selectedInfoLabels[colorIdx];
                    const assignedSummaryMetric = selectedSummaryMetrics[linestyleIdx];
                    const infoKey = assignedInfoLabel === '' || assignedInfoLabel === '<none>' ? '<none>' : assignedInfoLabel;
                    const dataKey = metric_name + '|' + infoKey + '|' + assignedSummaryMetric;
                    const newData = theDataDict[dataKey];

                    if (newData) {
                        source.data = {
                            transition_date: newData.transition_date,
                            transition_date_labels: newData.transition_date_labels,
                            summary_value: newData.summary_value,
                            run_name: newData.run_name,
                            info_label: Array(newData.transition_date.length).fill(assignedInfoLabel),
                            summary_metric: Array(newData.transition_date.length).fill(assignedSummaryMetric)
                        };
                        source.change.emit();
                        updatedCount++;
                    } else {
                        source.data = {
                            transition_date: [],
                            transition_date_labels: [],
                            summary_value: [],
                            run_name: [],
                            info_label: [],
                            summary_metric: []
                        };
                        source.change.emit();
                    }
                } else {
                    source.data = {
                        transition_date: [],
                        transition_date_labels: [],
                        summary_value: [],
                        run_name: [],
                        info_label: [],
                        summary_metric: []
                    };
                    source.change.emit();
                }
            }
        }
        console.log('Updated', updatedCount, 'sources');

        // Update legend items
        for (let i = 0; i < num_colors; i++) {
            const legendItem = combinedLegend.items[i];
            if (i < selectedInfoLabels.length) {
                legendItem.label = selectedInfoLabels[i];
                legendItem.visible = true;
            } else {
                legendItem.visible = false;
            }
        }
        for (let i = 0; i < num_styles; i++) {
            const legendItem = combinedLegend.items[num_colors + i];
            if (i < selectedSummaryMetrics.length) {
                legendItem.label = selectedSummaryMetrics[i];
                legendItem.visible = true;
            } else {
                legendItem.visible = false;
            }
        }
    }

    // Dispatch: use inline data, cached fetch data, or fetch from URL
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
            });
    }
    ''')

    # Add change handlers to selectors
    metric_name_selector.js_on_change('value', callback_container)
    summary_metric_selector.js_on_change('value', callback_container)
    metric_info_selector.js_on_change('value', callback_container)

    # Pre-fetch data on document load when using external JSON
    if data_json_url is not None:
        prefetch_cb = bokeh.models.CustomJS(
            args={'data_json_url': data_json_url},
            code='''
                fetch(data_json_url)
                    .then(r => r.json())
                    .then(json => {
                        window._chimera_data = json.data_dict;
                        console.log('Pre-fetched chimera data');
                    });
            '''
        )
        p.js_on_event(bokeh.events.DocumentReady, prefetch_cb)

    # Layout: heading (optional), then selectors in a row, then plot with legends
    layout_elements = []

    if build_date:
        heading = bokeh.models.PreText(
            text=f"Chimera Metric Explorer (built: {build_date})",
            sizing_mode='stretch_width',
            height=30,
        )
        layout_elements.append(heading)

    # Selectors row at the top
    selectors_row = bokeh.layouts.Row(
        metric_name_selector,
        metric_info_selector,
        summary_metric_selector,
        sizing_mode='stretch_width',
    )
    layout_elements.append(selectors_row)

    # Plot goes below selectors
    layout_elements.append(p)

    layout = bokeh.layouts.Column(
        *layout_elements,
        sizing_mode='stretch_width',
    )

    return layout


def get_all_metric_data_dict(summary_df: pd.DataFrame) -> dict:
    """Create a dictionary mapping combined metric keys to their data.

    Uses normalized keys where empty metric_info_label becomes '<none>'.

    Parameters
    ----------
    summary_df : pd.DataFrame
        DataFrame from load_chimera_summary.

    Returns
    -------
    dict
        Dictionary mapping "metric_name|metric_info_label|summary_metric" keys
        (with '<none>' for empty info labels) to dict with transition_date
        (timestamps), transition_date_labels (ISO strings), summary_value,
        and run_name arrays.
    """
    result = {}
    for label, group in summary_df.groupby(['metric_name', 'metric_info_label', 'summary_metric']):
        # Create key from the three components (normalize empty to '<none>')
        metric_name = label[0]
        metric_info = label[1] if label[1] and not pd.isna(label[1]) else ''
        summary_metric = label[2]
        # Use normalized key with '<none>' for empty info labels
        info_display = '<none>' if metric_info == '' else metric_info
        key = f"{metric_name}|{info_display}|{summary_metric}"

        # Convert date objects to timestamps (milliseconds since epoch)
        timestamps = [datetime.combine(d, datetime.min.time()).timestamp() * 1000
                      for d in group['transition_date'].values]
        # Also keep ISO string labels for hover display
        date_labels = [d.strftime('%Y-%m-%d') for d in group['transition_date'].values]
        result[key] = {
            'transition_date': timestamps,
            'transition_date_labels': date_labels,
            'summary_value': group['summary_value'].values,
            'run_name': group['run_name'].values,
        }
    return result


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        return super().default(obj)


def save_metric_data_json(
    summary_df: pd.DataFrame,
    unique_metrics: pd.DataFrame,
    json_path: str,
) -> None:
    """Save metric data and cascading dropdown mappings to a JSON file.

    Parameters
    ----------
    summary_df : pd.DataFrame
        DataFrame from load_chimera_summary containing all metric values.
    unique_metrics : pd.DataFrame
        DataFrame of unique metrics for building cascading mappings.
    json_path : str
        Path where the JSON file will be written.
    """
    data_dict = get_all_metric_data_dict(summary_df)

    def normalize_info_label(ml):
        return '<none>' if ml == '' or pd.isna(ml) else ml

    metric_to_info = {}
    metric_info_to_summary = {}
    for _, row in unique_metrics.iterrows():
        mn = row['metric_name']
        mili = row['metric_info_label']
        sm = row['summary_metric']
        if mn not in metric_to_info:
            metric_to_info[mn] = set()
        metric_to_info[mn].add(mili)
        key = (mn, mili)
        if key not in metric_info_to_summary:
            metric_info_to_summary[key] = set()
        metric_info_to_summary[key].add(sm)

    metric_to_info_json = {
        mn: [normalize_info_label(ml) for ml in sorted(info_labels)]
        for mn, info_labels in metric_to_info.items()
    }
    metric_info_to_summary_json = {
        f"{mn}|{normalize_info_label(ml)}": sorted(summary_metrics)
        for (mn, ml), summary_metrics in metric_info_to_summary.items()
    }

    output = {
        'data_dict': data_dict,
        'metric_to_info': metric_to_info_json,
        'metric_info_to_summary': metric_info_to_summary_json,
    }

    # json.dump writes Python float('nan') as bare NaN, which is not valid JSON.
    # Replace with null so browsers can parse the file.
    import re as _re
    raw = json.dumps(output, cls=_NumpyEncoder)
    raw = _re.sub(r'\bNaN\b', 'null', raw)
    with open(json_path, 'w') as f:
        f.write(raw)

