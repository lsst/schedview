============================================================
Design: Summary Metric Plotter
============================================================

Overview
--------

This design describes a tool for interactive visualization of MAF summary
metrics from a ``rubin_sim`` results database (``resultsDb_sqlite.db``).  The
tool enables users to select metrics via dropdown widgets, overplot multiple
info labels (distinguished by color) and multiple summary statistics
(distinguished by line style), and inspect individual data points via hover
tooltips.

The tool produces a pair of output files:

- An **HTML file** containing the interactive Bokeh visualization with widget
  controls.
- A **JSON file** containing the metric data, fetched at runtime by the HTML
  visualization.

This separation keeps the HTML small and allows the JSON data file to be
swapped without regenerating the HTML (e.g., to point at a different database
or a more recent run).

The tool is exposed as a command-line executable that accepts a results
database path and produces the HTML + JSON file pair.


Motivation
----------

The chimera progress capability generates summary tables with metrics tracked
across multiple transition dates.  These results are stored in a ``ResultsDb``
SQLite database and are difficult to explore interactively.  An interactive
Bokeh plot enables users to:

- Select which metric to visualize via dropdown
- Overplot multiple info labels (different colors)
- Overplot multiple summary statistics (different line styles)
- Inspect individual data points via hover tooltips
- Assess how metric values change over transition dates in chimera runs

This supports the survey performance monitoring goals outlined in RTN-092.


Architecture
------------

Following the ``schedview`` workflow (collect → compute → plot → report), the
summary metric plotter is decomposed into:

1. **Collect** — ``schedview.collect.maf_summary.load_maf_summary``: queries
   the results database and returns normalized DataFrames.
2. **Plot** — ``schedview.plot.maf_summary.make_metric_selector_plot``:
   takes the collected DataFrames, performs all necessary reshaping
   internally (timestamp conversion, cascading dropdown mappings, data
   dictionaries), and creates the interactive Bokeh layout with widgets and
   CustomJS callbacks.  A companion function ``save_metric_data_json``
   serializes the data the plot needs into an external JSON file.
3. **Report** — ``schedview.examples.summary_metric_plotter``: the
   command-line executable that drives the full workflow and writes the output
   files.

There is no separate compute module.  The transformations between collection
and plotting (building timestamp arrays, cascading dropdown mappings, and
metric-keyed data dictionaries) are entirely shaped by the needs of the Bokeh
visualization — they have no independent reuse value outside of this specific
plot.  Per the schedview architecture (RTN-092), the compute phase should
contain "only code that is independent of data retrieval or visual
representation."  Since all the intermediate data structures here are
determined by the plot's JavaScript callback contract, they belong inside the
plot module as private helpers.


Module Locations
----------------

::

    schedview/collect/maf_summary.py
    schedview/plot/maf_summary.py
    schedview/examples/summary_metric_plotter.py

.. code-block:: mermaid

    graph LR
        subgraph "schedview package"
            COLLECT[schedview.collect.maf_summary]
            PLOT[schedview.plot.maf_summary]
            REPORT[schedview.examples.summary_metric_plotter]
        end

        subgraph "External"
            DB[(ResultsDb)]
            HTML[output.html]
            JSON[output_data.json]
        end

        subgraph "Dependencies"
            PD[pandas]
            BK[bokeh]
            SQL[sqlite3]
            CL[click]
        end

        REPORT --> COLLECT
        REPORT --> PLOT
        COLLECT --> SQL
        COLLECT --> PD
        PLOT --> BK
        PLOT --> PD
        REPORT --> CL

        DB --> COLLECT
        PLOT --> HTML
        PLOT --> JSON


Package Registration
--------------------

The new modules must be registered in the existing ``__init__.py`` files.

``schedview/collect/__init__.py``:

- Add ``"load_maf_summary"`` to the ``__all__`` list.
- Add at the bottom (after the other unconditional imports):

  .. code-block:: python

      from .maf_summary import load_maf_summary

``schedview/plot/__init__.py``:

- Add ``"make_metric_selector_plot"`` and ``"save_metric_data_json"`` to
  the ``__all__`` list.
- Add at the bottom:

  .. code-block:: python

      from .maf_summary import make_metric_selector_plot, save_metric_data_json

The examples module does not have an ``__init__.py`` that exports symbols;
the CLI is invoked via ``python -m schedview.examples.summary_metric_plotter``.


Collect: ``schedview.collect.maf_summary``
------------------------------------------

Complete module implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """Load MAF summary metrics from a ResultsDb SQLite database."""

    __all__ = ["load_maf_summary"]

    import sqlite3
    from datetime import datetime

    import pandas as pd


    def load_maf_summary(
        db_path: str,
        run_name_pattern: str = "chimera_%",
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load and preprocess MAF summary data from a ResultsDb database.

        Queries the database for all runs matching ``run_name_pattern`` and
        returns a DataFrame with one row per metric per run, plus a
        deduplicated DataFrame of unique metric labels for selector dropdowns.

        Parameters
        ----------
        db_path : str
            Path to the resultsDb_sqlite.db file.
        run_name_pattern : str, optional
            SQL LIKE pattern to filter ``run_name`` values.  Defaults to
            ``"chimera_%"`` to select chimera runs.

        Returns
        -------
        summary_df : pd.DataFrame
            DataFrame with columns: run_name, metric_name, slicer_name,
            metric_info_label, summary_metric, summary_value,
            transition_dayobs, transition_date.
        unique_metrics : pd.DataFrame
            Deduplicated and sorted DataFrame of unique (metric_name,
            slicer_name, metric_info_label, summary_metric) combinations.

        Raises
        ------
        sqlite3.OperationalError
            If the database file does not exist or cannot be opened.
        """
        conn = sqlite3.connect(db_path)
        query = """
        SELECT
            m.run_name,
            m.metric_name,
            m.slicer_name,
            m.metric_info_label,
            ss.summary_name AS summary_metric,
            ss.summary_value
        FROM metrics m
        JOIN summarystats ss ON m.metric_id = ss.metric_id
        WHERE m.run_name LIKE ?
        ORDER BY m.run_name, m.metric_name, m.slicer_name,
                 m.metric_info_label, ss.summary_name
        """
        df = pd.read_sql_query(query, conn, params=(run_name_pattern,))
        conn.close()

        # Extract transition_dayobs from run_name.
        # For "chimera_20251031" this yields 20251031.
        # Uses the portion after the last underscore.
        df["transition_dayobs"] = df["run_name"].apply(
            lambda x: int(x.rsplit("_", 1)[1])
        )
        df["transition_date"] = df["transition_dayobs"].apply(
            lambda d: datetime.strptime(str(d), "%Y%m%d").date()
        )

        # Deduplicated unique metrics for dropdown options
        unique_metrics = (
            df.drop_duplicates(
                subset=[
                    "metric_name",
                    "slicer_name",
                    "metric_info_label",
                    "summary_metric",
                ]
            )
            .sort_values(
                ["metric_name", "slicer_name", "metric_info_label", "summary_metric"]
            )
            .reset_index(drop=True)
        )

        return df, unique_metrics

Implementation notes:

- Uses a parameterized query (``?`` placeholder) to pass
  ``run_name_pattern``, avoiding SQL injection.
- ``rsplit("_", 1)[1]`` extracts the date portion after the last underscore,
  making it work for any prefix pattern (e.g. ``"chimera_"``, ``"sim_"``).
- The ``transition_date`` is a ``datetime.date`` object, not a ``datetime``.


Plot: ``schedview.plot.maf_summary``
------------------------------------

Module structure
~~~~~~~~~~~~~~~~

The module contains:

- Two **private helpers** (``_build_data_dict``, ``_build_cascading_maps``)
  that build the internal data structures.
- Two **public functions** (``make_metric_selector_plot``,
  ``save_metric_data_json``).
- One **private class** (``_NumpyEncoder``) for JSON serialization.

.. code-block:: python

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


Private helper: ``_build_data_dict``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def _build_data_dict(summary_df: pd.DataFrame) -> dict:
        """Build the metric data dictionary for JavaScript consumption.

        Groups summary_df by (metric_name, metric_info_label, summary_metric)
        and returns a dictionary mapping pipe-delimited keys to data arrays.

        Keys have the format "metric_name|info_label|summary_metric" where
        empty info labels are normalized to "<none>".

        Each value is a dict with keys:
        - "transition_date": list of float (ms since epoch)
        - "transition_date_labels": list of str ("YYYY-MM-DD")
        - "summary_value": list of float (may contain None for NaN)
        - "run_name": list of str
        """

Logic:

1. Group ``summary_df`` by ``["metric_name", "metric_info_label",
   "summary_metric"]``.
2. For each group, build a key: normalize empty/NaN info_label to
   ``"<none>"``, then join with ``"|"``.
3. Convert ``transition_date`` values to milliseconds since epoch:
   ``datetime.combine(d, datetime.min.time()).timestamp() * 1000``.
4. Convert ``transition_date`` values to ISO strings for hover labels.
5. Convert ``summary_value`` to a Python list (calling ``.tolist()`` on the
   numpy array).  NaN values will become ``float('nan')`` in the list; the
   JSON serialization step converts them to ``null``.
6. Convert ``run_name`` to a Python list.


Private helper: ``_build_cascading_maps``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def _build_cascading_maps(
        unique_metrics: pd.DataFrame,
    ) -> tuple[dict, dict]:
        """Build cascading dropdown mappings.

        Returns
        -------
        metric_to_info : dict
            Maps metric_name -> sorted list of normalized info labels.
        metric_info_to_summary : dict
            Maps "metric_name|info_label" -> sorted list of summary metrics.
        """

Logic:

1. Iterate over rows of ``unique_metrics``.
2. For each row, normalize ``metric_info_label`` (empty/NaN → ``"<none>"``).
3. Build ``metric_to_info``: accumulate info labels into sets per
   metric_name, then sort each set into a list.
4. Build ``metric_info_to_summary``: accumulate summary metrics into sets
   per ``"metric_name|info_label"`` key, then sort each set into a list.


Public function: ``make_metric_selector_plot``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

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
        summary_df : pd.DataFrame
            DataFrame from ``load_maf_summary`` containing all metric values.
        unique_metrics : pd.DataFrame
            DataFrame of unique metric labels for the selector dropdowns.
        build_date : str or None, optional
            Build date string to show in a heading above the plot.
        line_colors : list of str or None, optional
            Color values for info label differentiation.  Defaults to
            ``bokeh.palettes.Colorblind8``.
        line_styles : list of str or None, optional
            Line dash names for summary metric differentiation.  Defaults to
            ``list(bokeh.core.enums.LineDash)``.
        data_json_url : str or None, optional
            URL to external JSON data file.  When set, data is fetched at
            runtime via fetch().  When None, data is embedded inline.

        Returns
        -------
        layout : bokeh.layouts.Column
            Complete Bokeh layout ready for display or saving.
        """

Implementation Steps (in order)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Set up palettes**:

   .. code-block:: python

       line_colors = line_colors or list(bokeh.palettes.Colorblind8)
       line_styles = line_styles or list(bokeh.core.enums.LineDash)

2. **Build internal data structures** by calling ``_build_data_dict`` and
   ``_build_cascading_maps``.

3. **Compute ticker dates**: get sorted unique ``transition_date`` values
   from ``summary_df``, convert to ISO strings and millisecond timestamps.

4. **Determine initial selections**:

   - ``metric_names``: sorted list of keys from ``metric_to_info``.
   - ``default_metric_name``: ``metric_names[0]``.
   - ``default_info_labels``: ``metric_to_info[default_metric_name]``.
   - ``initial_info_selection``: first 2 info labels (or fewer if limited).
   - ``default_summary_metrics``: looked up via
     ``metric_info_to_summary[default_metric_name + "|" + initial_info_selection[0]]``.
   - ``initial_summary_selection``: first 2 summary metrics (or fewer).

5. **Create widgets**:

   - ``metric_name_selector``: ``bokeh.models.Select(value=..., options=metric_names, width=250)``
   - ``metric_info_selector``: ``bokeh.models.MultiSelect(value=initial_info_selection, options=default_info_labels, width=300, title="Metric Info Labels (select multiple to overplot):")``
   - ``summary_metric_selector``: ``bokeh.models.MultiSelect(value=initial_summary_selection, options=default_summary_metrics, width=300, title="Summary Metrics (select multiple to overplot):")``

6. **Create figure**:

   .. code-block:: python

       p = bokeh.plotting.figure(
           width=800,
           height=400,
           sizing_mode="stretch_width",
           x_axis_type="datetime",
           x_axis_label="Transition Date",
           y_axis_label="Summary Value",
           title=f"{default_metric_name} | {', '.join(initial_summary_selection)}",
           tools="pan,wheel_zoom,box_zoom,reset,hover,crosshair",
       )

7. **Set x-axis ticks**: use ``bokeh.models.FixedTicker(ticks=ticker_dates)``
   and ``p.xaxis.major_label_overrides`` to map timestamps to ISO strings.
   Set ``p.x_range = bokeh.models.Range1d(min(ticker_dates), max(ticker_dates))``.

8. **Pre-create sources**: nested list ``sources[color_idx][linestyle_idx]``.
   For each (color_idx, linestyle_idx) pair:

   - Create a ``ColumnDataSource`` with empty columns:
     ``transition_date``, ``transition_date_labels``, ``summary_value``,
     ``run_name``, ``info_label``, ``summary_metric``.
   - Add a ``p.scatter(...)`` renderer with the corresponding color and
     ``line_dash``.
   - Add a ``p.line(...)`` renderer with the corresponding color and
     ``line_dash``.

9. **Populate initial data**: for each (info_idx, summary_idx) in the
   initial selections, look up the data from ``data_dict`` using the key
   ``f"{default_metric_name}|{info_label}|{summary_metric}"`` and assign
   to ``sources[info_idx][summary_idx].data``.

10. **Configure hover tool**:

    .. code-block:: python

        p.hover.tooltips = [
            ("Date", "@transition_date_labels"),
            ("Value", "@summary_value{0.000}"),
            ("Run", "@run_name"),
            ("Info", "@info_label"),
            ("Summary Metric", "@summary_metric"),
        ]

11. **Create legend**: pre-create LegendItems for all possible colors (one
    per info label slot) and all possible line styles (one per summary metric
    slot).  Set initial labels and visibility based on the initial
    selections.  Add the legend to the figure with
    ``p.add_layout(legend, "below")``.

    For info label legend items, create invisible reference scatter
    renderers (single-point sources at ``ticker_dates[0]``, y=0) with the
    corresponding color.

    For summary metric legend items, create invisible reference line
    renderers with the corresponding line_dash in black.

12. **Build CustomJS callback**: pass all necessary references as ``args``.
    The JavaScript code handles:

    - Cascading dropdown updates when ``metric_name`` changes.
    - Data assignment to the correct sources based on current selections.
    - Clearing unused sources.
    - Updating legend item labels and visibility.
    - Updating the plot title.

    When ``data_json_url`` is ``None``, pass the full ``data_dict`` as
    inline data.  When set, pass ``null`` for ``data_dict`` and use
    ``fetch()`` with ``window._chimera_data`` caching.

13. **Attach callbacks**: call ``js_on_change("value", callback)`` on all
    three selectors.

14. **Pre-fetch on DocumentReady** (only when ``data_json_url`` is set):

    .. code-block:: python

        prefetch_cb = bokeh.models.CustomJS(
            args={"data_json_url": data_json_url},
            code="""
                fetch(data_json_url)
                    .then(r => r.json())
                    .then(json => {
                        window._chimera_data = json.data_dict;
                        console.log('Pre-fetched metric data');
                    });
            """,
        )
        p.js_on_event(bokeh.events.DocumentReady, prefetch_cb)

15. **Assemble layout**:

    .. code-block:: python

        layout_elements = []
        if build_date:
            heading = bokeh.models.PreText(
                text=f"Summary Metric Explorer (built: {build_date})",
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

        return bokeh.layouts.column(*layout_elements, sizing_mode="stretch_width")


CustomJS Callback (JavaScript)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The callback code must be a single string.  It is invoked whenever any of
the three selectors changes.  The full JavaScript logic:

.. code-block:: javascript

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
                selector_info.value = newInfoOptions.slice(0, Math.min(2, newInfoOptions.length));
            }

            // Update summary metrics for the first info label
            const firstInfoLabel = selector_info.value[0] || newInfoOptions[0];
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

    // Update plot title
    plot.title.text = metric_name + ' | ' + selector_summary.value.join(', ');

    function performUpdate(theDataDict) {
        const curInfoLabels = selector_info.value;
        const curSummaryMetrics = selector_summary.value;
        const numInfoLabels = curInfoLabels.length;
        const numSummaryMetrics = curSummaryMetrics.length;

        for (let colorIdx = 0; colorIdx < num_colors; colorIdx++) {
            for (let linestyleIdx = 0; linestyleIdx < num_styles; linestyleIdx++) {
                const source = sources[colorIdx][linestyleIdx];

                if (colorIdx < numInfoLabels && linestyleIdx < numSummaryMetrics) {
                    const assignedInfoLabel = curInfoLabels[colorIdx];
                    const assignedSummaryMetric = curSummaryMetrics[linestyleIdx];
                    const infoKey = (assignedInfoLabel === '' || assignedInfoLabel === '<none>')
                        ? '<none>' : assignedInfoLabel;
                    const dataKey = metric_name + '|' + infoKey + '|' + assignedSummaryMetric;
                    const newData = theDataDict[dataKey];

                    if (newData) {
                        source.data = {
                            transition_date: newData.transition_date,
                            transition_date_labels: newData.transition_date_labels,
                            summary_value: newData.summary_value,
                            run_name: newData.run_name,
                            info_label: Array(newData.transition_date.length).fill(assignedInfoLabel),
                            summary_metric: Array(newData.transition_date.length).fill(assignedSummaryMetric),
                        };
                    } else {
                        source.data = {
                            transition_date: [], transition_date_labels: [],
                            summary_value: [], run_name: [],
                            info_label: [], summary_metric: [],
                        };
                    }
                } else {
                    source.data = {
                        transition_date: [], transition_date_labels: [],
                        summary_value: [], run_name: [],
                        info_label: [], summary_metric: [],
                    };
                }
                source.change.emit();
            }
        }

        // Update legend items: first num_colors items are info labels,
        // next num_styles items are summary metrics
        for (let i = 0; i < num_colors; i++) {
            const legendItem = combinedLegend.items[i];
            if (i < curInfoLabels.length) {
                legendItem.label = curInfoLabels[i];
                legendItem.visible = true;
            } else {
                legendItem.visible = false;
            }
        }
        for (let i = 0; i < num_styles; i++) {
            const legendItem = combinedLegend.items[num_colors + i];
            if (i < curSummaryMetrics.length) {
                legendItem.label = curSummaryMetrics[i];
                legendItem.visible = true;
            } else {
                legendItem.visible = false;
            }
        }
    }

    // Dispatch: inline data, cached fetch data, or fetch from URL
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

The ``args`` dict passed to ``CustomJS`` must include:

.. code-block:: python

    args = {
        "selector_name": metric_name_selector,
        "selector_summary": summary_metric_selector,
        "selector_info": metric_info_selector,
        "plot": p,
        "sources": sources,  # nested list [color_idx][linestyle_idx]
        "num_colors": len(line_colors),
        "num_styles": len(line_styles),
        "data_dict": data_dict if data_json_url is None else None,
        "data_json_url": data_json_url,
        "metric_to_info": metric_to_info,
        "metric_info_to_summary": metric_info_to_summary,
        "combinedLegend": combined_legend,
    }

Note: Bokeh serializes Python ``None`` as JavaScript ``null``, nested Python
lists as JavaScript arrays, and Python dicts as JavaScript objects.  This is
why passing ``sources`` as a nested list works — Bokeh resolves the
ColumnDataSource references within the nested structure.


Public function: ``save_metric_data_json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def save_metric_data_json(
        summary_df: pd.DataFrame,
        unique_metrics: pd.DataFrame,
        json_path: str,
    ) -> None:
        """Save metric data and cascading dropdown mappings to a JSON file.

        The output file is loaded at runtime by the HTML visualization when
        ``data_json_url`` is set in ``make_metric_selector_plot``.

        Parameters
        ----------
        summary_df : pd.DataFrame
            DataFrame from ``load_maf_summary`` containing all metric values.
        unique_metrics : pd.DataFrame
            DataFrame of unique metrics for building cascading mappings.
        json_path : str
            Path where the JSON file will be written.
        """
        data_dict = _build_data_dict(summary_df)
        metric_to_info, metric_info_to_summary = _build_cascading_maps(unique_metrics)

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


Private class: ``_NumpyEncoder``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

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


Report: ``schedview.examples.summary_metric_plotter``
-----------------------------------------------------

This module provides the command-line executable that drives the full
workflow.

Complete module implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """Command-line tool to generate a Summary Metric Explorer HTML file.

    Usage::

        python -m schedview.examples.summary_metric_plotter \\
            /path/to/resultsDb_sqlite.db output.html
    """

    import os
    from datetime import datetime

    import bokeh.io
    import click

    from schedview.collect.maf_summary import load_maf_summary
    from schedview.plot.maf_summary import make_metric_selector_plot, save_metric_data_json


    def make_summary_metric_plot(
        db_path: str,
        output_html: str,
        build_date: str | None = None,
        title: str = "Summary Metric Explorer",
        run_name_pattern: str = "chimera_%",
    ) -> None:
        """Generate an interactive Summary Metric Explorer HTML file.

        Parameters
        ----------
        db_path : str
            Path to the ResultsDb SQLite database file.
        output_html : str
            Path for the output HTML file.
        build_date : str or None, optional
            Build date string for the heading.  If None, uses current datetime.
        title : str, optional
            HTML page title.
        run_name_pattern : str, optional
            SQL LIKE pattern to filter run names.
        """
        if build_date is None:
            build_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Collect
        summary_df, unique_metrics = load_maf_summary(db_path, run_name_pattern)

        # Derive JSON path from HTML path
        if output_html.endswith(".html"):
            json_path = output_html[:-5] + "_data.json"
        else:
            json_path = output_html + "_data.json"

        # Save JSON data file
        save_metric_data_json(summary_df, unique_metrics, json_path)

        # Plot
        data_json_url = os.path.basename(json_path)
        plot = make_metric_selector_plot(
            summary_df, unique_metrics, build_date, data_json_url=data_json_url
        )

        # Report
        bokeh.io.output_file(filename=output_html, title=f"{title} (built: {build_date})")
        bokeh.io.save(plot)

        print(f"Saved to {output_html}")
        print(f"Data written to {json_path}")


    @click.command()
    @click.argument("db_path", type=click.Path(exists=True))
    @click.argument("output_html", type=click.Path())
    @click.option(
        "--build-date", "-d", default=None,
        help="Build date string for heading. Defaults to current datetime.",
    )
    @click.option(
        "--title", "-t", default="Summary Metric Explorer",
        help="HTML page title.",
    )
    @click.option(
        "--run-name-pattern", "-p", default="chimera_%",
        help="SQL LIKE pattern to filter run names.",
    )
    def main(db_path, output_html, build_date, title, run_name_pattern):
        """Generate an interactive Summary Metric Explorer HTML file.

        DB_PATH is the path to a ResultsDb SQLite database.
        OUTPUT_HTML is the path where the output HTML file will be written.
        A companion JSON data file is written alongside the HTML file.
        """
        make_summary_metric_plot(db_path, output_html, build_date, title, run_name_pattern)


    if __name__ == "__main__":
        main()


Data Flow
---------

.. code-block:: mermaid

    graph TD
        DB[(ResultsDb SQLite)] -->|collect| LMS[load_maf_summary]
        LMS --> SDF[summary_df]
        LMS --> UM[unique_metrics]

        SDF --> SMJSON[save_metric_data_json]
        UM --> SMJSON
        SMJSON -->|write| JSON[_data.json]

        SDF --> MMSP[make_metric_selector_plot]
        UM --> MMSP
        MMSP -->|plot| LAYOUT[bokeh.layouts.Column]

        LAYOUT --> SAVE[bokeh.io.save]
        SAVE -->|report| HTML[output.html]

        JSON -.->|fetch at runtime| HTML


JSON Data File Format
---------------------

The JSON file written by ``save_metric_data_json`` contains all the data
structures that the plot's JavaScript callbacks require at runtime:

.. code-block:: json

    {
      "data_dict": {
        "metric_name|info_label|summary_metric": {
          "transition_date": [<timestamps in ms>],
          "transition_date_labels": ["YYYY-MM-DD", ...],
          "summary_value": [<floats or null>],
          "run_name": ["chimera_YYYYMMDD", ...]
        }
      },
      "metric_to_info": {
        "metric_name": ["info_label_1", ...]
      },
      "metric_info_to_summary": {
        "metric_name|info_label": ["summary_metric_1", ...]
      }
    }

Including the cascading mappings in the JSON file (alongside the data
dictionary) ensures that a future file-selector widget can fully swap all
per-database state by loading a different JSON file.


Deployment
----------

**Runtime Dependencies**:

- ``pandas``
- ``bokeh``
- ``sqlite3`` (standard library)
- ``click`` (for CLI)
- ``numpy`` (for type handling in JSON serialization)

**No Bokeh server required**: all interactivity is client-side via CustomJS.

**Output artifacts**: The executable produces two files that must be served
from the same directory (or the JSON URL must be adjusted):

- ``output.html`` — the interactive visualization
- ``output_data.json`` — the metric data fetched at runtime

These can be served by any static web server (nginx, S3, GitHub Pages, etc.)
or opened directly in a browser (if the browser supports ``fetch()`` on
local files, or a local server is used).


Integration with Jupyter Notebooks
-----------------------------------

The collect and plot functions can also be used directly in Jupyter notebooks
without the CLI:

.. code-block:: python

    import bokeh.io
    from bokeh.plotting import show

    from schedview.collect.maf_summary import load_maf_summary
    from schedview.plot.maf_summary import make_metric_selector_plot

    bokeh.io.output_notebook()

    # Collect
    summary_df, unique_metrics = load_maf_summary(db_path)

    # Plot (inline data, no external JSON needed)
    plot = make_metric_selector_plot(summary_df, unique_metrics)
    show(plot)

When used in a notebook, omitting ``data_json_url`` embeds all metric data
inline in the Bokeh document for self-contained display.


Quality Attributes
------------------

Testability
~~~~~~~~~~~

- **Isolated I/O**: ``load_maf_summary`` performs only a database read and
  can be tested against a fixture database or mocked.
- **Structural verification**: the Bokeh layout returned by
  ``make_metric_selector_plot`` can be inspected programmatically for
  expected widget types, renderer count, and legend structure.
- **JSON round-trip**: ``save_metric_data_json`` output can be verified by
  loading with ``json.load`` and checking structure and types.

Performance
~~~~~~~~~~~

- All data loaded into memory (acceptable for typical chimera runs <100K
  rows).
- Source pre-allocation is O(1): ``len(line_colors) × len(line_styles)``
  (default 64 with Colorblind8 × LineDash).
- Client-side filtering scales with the number of active data series
  (recommended cap: ~20 simultaneous series).

Maintainability
~~~~~~~~~~~~~~~

- Follows the ``schedview`` architecture (collect/plot/report), omitting the
  compute phase where it would add no reuse value.
- Type hints on all function signatures.
- NumPyDoc-style docstrings.
- Line length compatible with black (88 characters).


Dependencies
------------

- ``pandas``
- ``numpy``
- ``bokeh`` (plotting, models, palettes, core.enums, events, layouts, io)
- ``sqlite3`` (standard library)
- ``click`` (CLI)
- ``json`` (standard library)
- ``datetime`` (standard library)
- ``os`` (standard library)


Changes from Prototype
----------------------

The prototype (``tmp/chimera_explore.py``) is a single-file script that
combines all phases.  This design refactors it into the ``schedview``
architecture:

1. **Separation of concerns**: database access is isolated in a collect
   module; Bokeh plot creation and data serialization live in a plot module;
   CLI orchestration is in the examples module.
2. **Integration with schedview package**: functions are importable from
   ``schedview.collect`` and ``schedview.plot``.
3. **Configurable run pattern**: the ``run_name_pattern`` parameter allows
   the tool to be used with non-chimera databases.
4. **Notebook-friendly**: collect and plot can be called independently in a
   Jupyter notebook without the CLI.
5. **No artificial compute layer**: the prototype's data reshaping
   (timestamp conversion, dropdown mappings) stays inside the plot module
   where it belongs, rather than being promoted to a separate compute step
   that has no independent reuse.
6. **Preserved from prototype**:

   - External JSON + HTML file pair output
   - ``DocumentReady`` pre-fetch of JSON data
   - Cascading dropdown logic (metric → info labels → summary metrics)
   - Source pre-allocation with configurable colors and line styles
   - Combined legend with visibility toggling
   - Hover tooltips
   - ``click``-based CLI


Reference: Prototype Function Mapping
--------------------------------------

This table shows where each prototype function ends up:

.. list-table::
   :header-rows: 1

   * - Prototype function
     - New location
     - New name
   * - ``load_chimera_summary``
     - ``schedview.collect.maf_summary``
     - ``load_maf_summary``
   * - ``get_all_metric_data_dict``
     - ``schedview.plot.maf_summary``
     - ``_build_data_dict`` (private)
   * - ``make_metric_selector_plot``
     - ``schedview.plot.maf_summary``
     - ``make_metric_selector_plot``
   * - ``save_metric_data_json``
     - ``schedview.plot.maf_summary``
     - ``save_metric_data_json``
   * - ``_NumpyEncoder``
     - ``schedview.plot.maf_summary``
     - ``_NumpyEncoder`` (private)
   * - ``main`` (click CLI)
     - ``schedview.examples.summary_metric_plotter``
     - ``main``
   * - (new)
     - ``schedview.examples.summary_metric_plotter``
     - ``make_summary_metric_plot``
   * - (inline in ``make_metric_selector_plot``)
     - ``schedview.plot.maf_summary``
     - ``_build_cascading_maps`` (private)
