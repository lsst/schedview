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


Collect: ``schedview.collect.maf_summary``
------------------------------------------

Public function: ``load_maf_summary``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def load_maf_summary(
        db_path: str,
        run_name_pattern: str = "chimera_%",
    ) -> tuple[pd.DataFrame, pd.DataFrame]:

Parameters
^^^^^^^^^^

``db_path`` : ``str``
    Path to the ``resultsDb_sqlite.db`` file.

``run_name_pattern`` : ``str``
    SQL LIKE pattern to filter ``run_name`` values.  Defaults to
    ``"chimera_%"`` to select chimera runs.

Returns
^^^^^^^

A tuple of two DataFrames:

- ``summary_df``: One row per (run, metric, slicer, info_label,
  summary_metric) combination.  Columns:

  .. list-table::
     :header-rows: 1

     * - Column
       - Type
       - Description
     * - ``run_name``
       - str
       - Run identifier (e.g., ``"chimera_20251031"``)
     * - ``metric_name``
       - str
       - Name of the computed metric
     * - ``slicer_name``
       - str
       - Slicer used for spatial/temporal binning
     * - ``metric_info_label``
       - str
       - Additional info label (may be empty)
     * - ``summary_metric``
       - str
       - Aggregated statistic name (e.g., ``"Mean"``, ``"Median"``)
     * - ``summary_value``
       - float
       - Computed summary value
     * - ``transition_dayobs``
       - int
       - dayObs integer (YYYYMMDD) extracted from ``run_name``
     * - ``transition_date``
       - datetime.date
       - Python date object derived from ``transition_dayobs``

- ``unique_metrics``: Deduplicated set of (``metric_name``,
  ``slicer_name``, ``metric_info_label``, ``summary_metric``) tuples,
  sorted for predictable ordering.

Raises
^^^^^^

``sqlite3.OperationalError``
    If the database file does not exist or cannot be opened.

SQL Query
^^^^^^^^^

.. code-block:: sql

    SELECT
        m.run_name,
        m.metric_name,
        m.slicer_name,
        m.metric_info_label,
        ss.summary_name AS summary_metric,
        ss.summary_value
    FROM metrics m
    JOIN summarystats ss ON m.metric_id = ss.metric_id
    WHERE m.run_name LIKE :run_name_pattern
    ORDER BY m.run_name, m.metric_name, m.slicer_name,
             m.metric_info_label, ss.summary_name

Implementation Notes
^^^^^^^^^^^^^^^^^^^^

- The ``transition_dayobs`` is extracted from ``run_name`` by stripping the
  prefix up to the last underscore and parsing the remainder as an integer.
  For the default ``"chimera_%"`` pattern, this yields the YYYYMMDD date from
  ``"chimera_20251031"`` → ``20251031``.
- The ``transition_date`` column is derived by parsing ``transition_dayobs``
  with ``datetime.strptime(str(d), '%Y%m%d').date()``.
- Empty ``metric_info_label`` values are preserved as empty strings in the
  DataFrame (normalization to ``"<none>"`` for display is handled internally
  by the plot module).


Plot: ``schedview.plot.maf_summary``
------------------------------------

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

Parameters
^^^^^^^^^^

``summary_df`` : ``pd.DataFrame``
    DataFrame from ``load_maf_summary`` containing all metric values.

``unique_metrics`` : ``pd.DataFrame``
    DataFrame of unique metric labels for the selector dropdowns.

``build_date`` : ``str | None``
    Optional build date string to show in a heading above the plot.

``line_colors`` : ``list[str] | None``
    List of color values (hex strings or named colors).  If ``None``, uses
    ``bokeh.palettes.Colorblind8`` (8 colors).

``line_styles`` : ``list[str] | None``
    List of line dash names.  If ``None``, uses
    ``bokeh.core.enums.LineDash`` values.

``data_json_url`` : ``str | None``
    URL (relative or absolute) to an external JSON data file.  When set,
    the CustomJS callback fetches data at runtime via ``fetch()`` instead of
    embedding it inline.  A ``DocumentReady`` callback pre-fetches the data.
    When ``None`` (default), the full data dictionary is embedded inline in
    the Bokeh document.

Returns
^^^^^^^

A ``bokeh.layouts.Column`` containing:

- An optional ``PreText`` heading (if ``build_date`` is provided)
- A ``Row`` of selector widgets:

  - ``Select`` widget for ``metric_name`` (single selection)
  - ``MultiSelect`` widget for ``metric_info_label`` (multi-selection,
    color-coded)
  - ``MultiSelect`` widget for ``summary_metric`` (multi-selection,
    line-style-coded)

- A ``Figure`` with datetime x-axis, scatter + line renderers, hover
  tooltips, and a combined legend

Internal Reshaping
^^^^^^^^^^^^^^^^^^

The function internally builds the data structures needed by its JavaScript
callbacks.  These are private implementation details, not part of the public
API:

- **Data dictionary**: groups ``summary_df`` by (metric_name,
  metric_info_label, summary_metric), converting dates to millisecond
  timestamps and normalizing empty info labels to ``"<none>"``.
- **Cascading dropdown mappings**: ``metric_to_info`` and
  ``metric_info_to_summary`` dictionaries derived from ``unique_metrics``.
- **Ticker dates**: unique transition dates converted to timestamps for the
  x-axis.

Widget and Callback Behavior
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: mermaid

    flowchart TD
        MN[Select: metric_name] -->|on change| CB[CustomJS Callback]
        MI[MultiSelect: metric_info_label] -->|on change| CB
        SM[MultiSelect: summary_metric] -->|on change| CB

        CB --> CASCADE{metric_name changed?}
        CASCADE -->|yes| UPDATE_MI[Update info_label options]
        UPDATE_MI --> UPDATE_SM[Update summary_metric options]
        CASCADE -->|no| ASSIGN

        UPDATE_SM --> ASSIGN[Assign data to sources]
        ASSIGN --> SRC["sources[color_idx][linestyle_idx]"]
        ASSIGN --> EMPTY[Empty unused sources]
        ASSIGN --> LEG[Update legend labels/visibility]

**Cascading dropdowns**: When the user selects a different ``metric_name``,
the ``metric_info_label`` MultiSelect options are updated to show only valid
info labels for that metric, and the ``summary_metric`` MultiSelect options
are updated to show only valid summary metrics for the selected
(metric_name, info_label) combination.

**Source pre-allocation**: The function pre-creates
``len(line_colors) × len(line_styles)`` ColumnDataSources, each with a
unique (color, line_dash) combination.  When the user makes selections:

- Each selected info_label is assigned a color (by selection index)
- Each selected summary_metric is assigned a line style (by selection index)
- Data is assigned to the source at ``sources[color_idx][linestyle_idx]``

Sources not used by the current selection are emptied.

**Combined legend**: A single Legend with pre-created LegendItems for all
possible colors (info labels) and line styles (summary metrics).  JavaScript
callbacks update labels and visibility when selections change, avoiding
recreation of legend items.

**Hover tooltips**: Date, Value, Run, Info Label, Summary Metric.

**Client-side only**: All interactivity is via CustomJS callbacks.  No Bokeh
server is required.


Public function: ``save_metric_data_json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def save_metric_data_json(
        summary_df: pd.DataFrame,
        unique_metrics: pd.DataFrame,
        json_path: str,
    ) -> None:

Parameters
^^^^^^^^^^

``summary_df`` : ``pd.DataFrame``
    DataFrame from ``load_maf_summary`` containing all metric values.

``unique_metrics`` : ``pd.DataFrame``
    DataFrame of unique metrics for building cascading mappings.

``json_path`` : ``str``
    Path where the JSON file will be written.

Implementation Notes
^^^^^^^^^^^^^^^^^^^^

- Builds the same internal data structures as ``make_metric_selector_plot``
  (data dictionary, cascading mappings, ticker dates) and serializes them
  to JSON.
- Uses a custom encoder to handle any residual numpy types (``np.integer``,
  ``np.floating``, ``np.ndarray``).
- Replaces bare ``NaN`` tokens with ``null`` in the output (since
  ``json.dumps`` emits non-standard ``NaN`` for Python ``float('nan')``).
- The internal reshaping logic is shared with ``make_metric_selector_plot``
  via private helper functions within the module.


Report: ``schedview.examples.summary_metric_plotter``
-----------------------------------------------------

This module provides the command-line executable that drives the full
workflow.

Public function: ``make_summary_metric_plot``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def make_summary_metric_plot(
        db_path: str,
        output_html: str,
        build_date: str | None = None,
        title: str = "Summary Metric Explorer",
        run_name_pattern: str = "chimera_%",
    ) -> None:

Parameters
^^^^^^^^^^

``db_path`` : ``str``
    Path to the ResultsDb SQLite database file.

``output_html`` : ``str``
    Path for the output HTML file.

``build_date`` : ``str | None``
    Build date string for the heading.  If ``None``, the current datetime
    is used.

``title`` : ``str``
    HTML ``<title>`` tag text.

``run_name_pattern`` : ``str``
    SQL LIKE pattern to filter runs.

Implementation Steps
^^^^^^^^^^^^^^^^^^^^

1. Generate ``build_date`` from ``datetime.now()`` if not provided.
2. **Collect**: call ``load_maf_summary(db_path, run_name_pattern)``.
3. **Save JSON**: derive ``json_path`` from ``output_html`` (replace
   ``.html`` suffix with ``_data.json``).  Call
   ``save_metric_data_json(summary_df, unique_metrics, json_path)``.
4. **Plot**: call ``make_metric_selector_plot(summary_df, unique_metrics,
   build_date, data_json_url=os.path.basename(json_path))``.
5. **Report**: call ``bokeh.io.output_file(filename=output_html,
   title=f"{title} (built: {build_date})")`` followed by
   ``bokeh.io.save(plot)``.
6. Print confirmation messages to stdout.


CLI Entry Point
^^^^^^^^^^^^^^^

The module provides a ``click``-based CLI entry point:

.. code-block:: python

    @click.command()
    @click.argument("db_path", type=click.Path(exists=True))
    @click.argument("output_html", type=click.Path())
    @click.option("--build-date", "-d", default=None,
                  help="Build date string for heading.")
    @click.option("--title", "-t", default="Summary Metric Explorer",
                  help="HTML page title.")
    @click.option("--run-name-pattern", "-p", default="chimera_%",
                  help="SQL LIKE pattern to filter run names.")
    def main(db_path, output_html, build_date, title, run_name_pattern):

The ``main`` function calls ``make_summary_metric_plot`` and is guarded by
``if __name__ == "__main__": main()``.

Usage Examples
^^^^^^^^^^^^^^

Basic usage (produces HTML + JSON)::

    python -m schedview.examples.summary_metric_plotter \
        /path/to/resultsDb_sqlite.db output.html

Custom options::

    python -m schedview.examples.summary_metric_plotter \
        /path/to/resultsDb_sqlite.db output.html \
        --build-date "2026-07-06 12:00:00" \
        --title "Chimera Metric Explorer" \
        --run-name-pattern "chimera_%"


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

The prototype (``chimera_explore.py``) is a single-file script that combines
all phases.  This design refactors it into the ``schedview`` architecture:

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
