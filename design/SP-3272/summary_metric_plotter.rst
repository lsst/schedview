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

Module structure
~~~~~~~~~~~~~~~~

The module contains:

- One **private helper** (``_extract_transition_date``) for defensive date
  parsing from run names.
- One **public function** (``load_maf_summary``) that queries the database
  and returns normalized DataFrames.

The module is importable from ``schedview.collect``:

>>> from schedview.collect.maf_summary import load_maf_summary
>>> load_maf_summary.__module__
'schedview.collect.maf_summary'


Private helper: ``_extract_transition_date``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extracts a ``datetime.date`` from a run_name by matching an 8-digit
YYYYMMDD pattern at the end of the string.  Returns ``None`` if parsing
fails.

>>> from schedview.collect.maf_summary import _extract_transition_date
>>> from datetime import date

**Normal chimera run names**:

>>> _extract_transition_date("chimera_20251031")
datetime.date(2025, 10, 31)

**Multi-underscore prefixes**:

>>> _extract_transition_date("some_long_prefix_20260101")
datetime.date(2026, 1, 1)

**No valid date suffix** — returns ``None``:

>>> _extract_transition_date("badname") is None
True
>>> _extract_transition_date("chimera_notadate") is None
True

**Invalid date digits** (e.g. month 13) — returns ``None``:

>>> _extract_transition_date("chimera_20251301") is None
True


Public function: ``load_maf_summary``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Queries the ResultsDb SQLite database for runs matching
``run_name_pattern`` and returns two DataFrames: the full summary data
and a deduplicated table of unique metric labels.

**Signature and return types**:

>>> import inspect
>>> sig = inspect.signature(load_maf_summary)
>>> sorted(sig.parameters.keys())
['db_path', 'run_name_pattern']
>>> sig.parameters['run_name_pattern'].default
'chimera_%'

**Functional test with a fixture database**:

>>> import sqlite3, tempfile, os
>>> tmpdir = tempfile.mkdtemp()
>>> db_path = os.path.join(tmpdir, "test.db")
>>> conn = sqlite3.connect(db_path)
>>> _ = conn.execute(
...     "CREATE TABLE metrics (metric_id INTEGER PRIMARY KEY,"
...     " run_name TEXT, metric_name TEXT,"
...     " slicer_name TEXT, metric_info_label TEXT)")
>>> _ = conn.execute(
...     "CREATE TABLE summarystats (stat_id INTEGER PRIMARY KEY,"
...     " metric_id INTEGER, summary_name TEXT,"
...     " summary_value REAL)")
>>> _ = conn.execute(
...     "INSERT INTO metrics VALUES"
...     " (1,'chimera_20251031','fO','HealpixSlicer','')")
>>> _ = conn.execute(
...     "INSERT INTO metrics VALUES"
...     " (2,'chimera_20251130','fO','HealpixSlicer','')")
>>> _ = conn.execute(
...     "INSERT INTO summarystats VALUES (1,1,'fOArea',100.0)")
>>> _ = conn.execute(
...     "INSERT INTO summarystats VALUES (2,2,'fOArea',150.0)")
>>> conn.commit()
>>> conn.close()
>>> summary_df, unique_metrics = load_maf_summary(db_path)

**Output columns**:

>>> sorted(summary_df.columns)
['metric_info_label', 'metric_name', 'run_name', 'slicer_name', 'summary_metric', 'summary_value', 'transition_date', 'transition_dayobs']

**Date parsing produces ``datetime.date`` objects**:

>>> from datetime import date
>>> summary_df["transition_date"].iloc[0] == date(2025, 10, 31)
True
>>> int(summary_df["transition_dayobs"].iloc[0])
20251031

**Unique metrics are deduplicated**:

>>> len(unique_metrics)
1
>>> unique_metrics["metric_name"].iloc[0]
'fO'

**Malformed run names raise ``ValueError`` when all rows are bad**:

>>> conn = sqlite3.connect(db_path)
>>> _ = conn.execute("DELETE FROM metrics")
>>> _ = conn.execute("DELETE FROM summarystats")
>>> _ = conn.execute(
...     "INSERT INTO metrics VALUES"
...     " (10,'badname','fO','Slicer','')")
>>> _ = conn.execute(
...     "INSERT INTO summarystats VALUES (10,10,'fOArea',99.0)")
>>> conn.commit()
>>> conn.close()
>>> try:
...     load_maf_summary(db_path, run_name_pattern="%")
... except ValueError as e:
...     "No rows with parseable transition dates" in str(e)
True

>>> import shutil
>>> shutil.rmtree(tmpdir)


Plot: ``schedview.plot.maf_summary``
------------------------------------

Module structure
~~~~~~~~~~~~~~~~

The module contains:

- Two **data-prep private helpers** (``_build_data_dict``,
  ``_build_cascading_maps``) that build the internal data structures.
- Three **plot-construction private helpers**
  (``_create_metric_selectors``, ``_preallocate_sources_and_renderers``,
  ``_create_combined_legend``) that decompose the Bokeh plot setup.
- One **module-level constant** (``_CALLBACK_CODE``) containing the
  CustomJS callback JavaScript with a contract comment.
- Two **public functions** (``make_metric_selector_plot``,
  ``save_metric_data_json``).
- One **private class** (``_NumpyEncoder``) for JSON serialization.

The public API is importable from ``schedview.plot``:

>>> from schedview.plot.maf_summary import (
...     make_metric_selector_plot, save_metric_data_json)
>>> make_metric_selector_plot.__module__
'schedview.plot.maf_summary'
>>> save_metric_data_json.__module__
'schedview.plot.maf_summary'


Private helper: ``_build_data_dict``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Groups ``summary_df`` by (metric_name, metric_info_label,
summary_metric) and returns a dictionary mapping pipe-delimited keys
to data arrays.  Empty info labels are normalized to ``"<none>"``.

>>> from schedview.plot.maf_summary import _build_data_dict
>>> from datetime import date
>>> import pandas as pd
>>> summary_df = pd.DataFrame({
...     "run_name": ["chimera_20251031", "chimera_20251130"],
...     "metric_name": ["fO", "fO"],
...     "slicer_name": ["HealpixSlicer", "HealpixSlicer"],
...     "metric_info_label": ["", ""],
...     "summary_metric": ["fOArea", "fOArea"],
...     "summary_value": [100.0, 150.0],
...     "transition_dayobs": [20251031, 20251130],
...     "transition_date": [date(2025, 10, 31), date(2025, 11, 30)],
... })
>>> data_dict = _build_data_dict(summary_df)

**Key format** — empty info labels become ``<none>``:

>>> sorted(data_dict.keys())
['fO|<none>|fOArea']

**Value structure** — each entry has timestamp, label, value, run arrays:

>>> sorted(data_dict["fO|<none>|fOArea"].keys())
['run_name', 'summary_value', 'transition_date', 'transition_date_labels']
>>> data_dict["fO|<none>|fOArea"]["summary_value"]
[100.0, 150.0]
>>> data_dict["fO|<none>|fOArea"]["transition_date_labels"]
['2025-10-31', '2025-11-30']
>>> data_dict["fO|<none>|fOArea"]["run_name"]
['chimera_20251031', 'chimera_20251130']

**Timestamps are milliseconds since epoch** (floats):

>>> all(isinstance(t, float)
...     for t in data_dict["fO|<none>|fOArea"]["transition_date"])
True

**Non-empty info labels are preserved**:

>>> df2 = summary_df.copy()
>>> df2["metric_info_label"] = ["g band", "g band"]
>>> d2 = _build_data_dict(df2)
>>> sorted(d2.keys())
['fO|g band|fOArea']


Private helper: ``_build_cascading_maps``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builds cascading dropdown mappings: ``metric_to_info`` maps each
metric_name to its sorted list of info labels, and
``metric_info_to_summary`` maps each ``"metric|info"`` key to its
sorted list of summary metrics.

>>> from schedview.plot.maf_summary import _build_cascading_maps
>>> unique_metrics = pd.DataFrame({
...     "run_name": ["chimera_20251031"] * 3,
...     "metric_name": ["fO", "fO", "SNR"],
...     "slicer_name": ["HealpixSlicer"] * 3,
...     "metric_info_label": ["", "g band", ""],
...     "summary_metric": ["fOArea", "fOArea", "Median"],
... })
>>> metric_to_info, metric_info_to_summary = (
...     _build_cascading_maps(unique_metrics))

**metric_to_info** — sorted info labels per metric:

>>> metric_to_info["fO"]
['<none>', 'g band']
>>> metric_to_info["SNR"]
['<none>']

**metric_info_to_summary** — summary metrics per metric|info key:

>>> metric_info_to_summary["fO|<none>"]
['fOArea']
>>> metric_info_to_summary["fO|g band"]
['fOArea']
>>> metric_info_to_summary["SNR|<none>"]
['Median']


Private helper: ``_create_metric_selectors``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates the three Bokeh selector widgets and determines initial
selections from the cascading maps.

>>> from schedview.plot.maf_summary import _create_metric_selectors
>>> import bokeh.models
>>> result = _create_metric_selectors(
...     metric_to_info, metric_info_to_summary)
>>> len(result)
6

**Returns a Select and two MultiSelects**:

>>> (metric_name_sel, info_sel, summary_sel,
...  init_info, init_summary, default_name) = result
>>> isinstance(metric_name_sel, bokeh.models.Select)
True
>>> isinstance(info_sel, bokeh.models.MultiSelect)
True
>>> isinstance(summary_sel, bokeh.models.MultiSelect)
True

**Default metric is first alphabetically**:

>>> default_name
'SNR'


Private helper: ``_preallocate_sources_and_renderers``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-creates a ``sources[color_idx][linestyle_idx]`` nested list of
``ColumnDataSource`` objects, each with scatter + line renderers.

>>> from schedview.plot.maf_summary import (
...     _preallocate_sources_and_renderers)
>>> import bokeh.plotting
>>> p = bokeh.plotting.figure(width=400, height=200)
>>> sources = _preallocate_sources_and_renderers(
...     p, ["red", "blue"], ["solid", "dashed"])
>>> len(sources)
2
>>> len(sources[0])
2
>>> isinstance(sources[0][0], bokeh.models.ColumnDataSource)
True

**Each source has the expected columns**:

>>> sorted(sources[0][0].data.keys())
['info_label', 'run_name', 'summary_metric', 'summary_value', 'transition_date', 'transition_date_labels']


Private helper: ``_create_combined_legend``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates the combined legend with invisible reference renderers for
color-coding (info labels) and line-style coding (summary metrics).

>>> from schedview.plot.maf_summary import _create_combined_legend
>>> p2 = bokeh.plotting.figure(width=400, height=200)
>>> legend, info_rend, summary_rend = _create_combined_legend(
...     p2, ["red", "blue"], ["solid", "dashed"],
...     [1000.0, 2000.0], ["label_a"], ["stat_1"])
>>> isinstance(legend, bokeh.models.Legend)
True
>>> len(info_rend)
2
>>> len(summary_rend)
2

**Legend items**: first N entries are for info labels (by color),
next M entries are for summary metrics (by line style):

>>> len(legend.items)
4
>>> legend.items[0].label.value
'label_a'
>>> legend.items[0].visible
True
>>> legend.items[1].visible
False


Public function: ``make_metric_selector_plot``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates the complete interactive Bokeh layout with selector widgets,
figure, legend, and CustomJS callbacks.

>>> from schedview.plot.maf_summary import make_metric_selector_plot
>>> import bokeh.layouts
>>> plot = make_metric_selector_plot(summary_df, unique_metrics)
>>> isinstance(plot, bokeh.layouts.Column)
True

**Without build_date**: layout has 2 children (selectors row + figure):

>>> len(plot.children)
2
>>> isinstance(plot.children[0], bokeh.layouts.Row)
True

**With build_date**: layout has 3 children (heading + selectors + figure):

>>> plot2 = make_metric_selector_plot(
...     summary_df, unique_metrics, build_date="2026-07-07")
>>> len(plot2.children)
3
>>> isinstance(plot2.children[0], bokeh.models.PreText)
True
>>> "2026-07-07" in plot2.children[0].text
True

**Selectors row contains 3 widgets**:

>>> selectors = plot.children[0]
>>> len(selectors.children)
3
>>> isinstance(selectors.children[0], bokeh.models.Select)
True
>>> isinstance(selectors.children[1], bokeh.models.MultiSelect)
True
>>> isinstance(selectors.children[2], bokeh.models.MultiSelect)
True

**External JSON URL mode** (data not embedded inline):

>>> plot3 = make_metric_selector_plot(
...     summary_df, unique_metrics, data_json_url="data.json")
>>> isinstance(plot3, bokeh.layouts.Column)
True


CustomJS Callback (``_CALLBACK_CODE``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The callback JavaScript is stored as a module-level string constant
``_CALLBACK_CODE``.  It is invoked whenever any of the three selectors
changes.

>>> from schedview.plot.maf_summary import _CALLBACK_CODE
>>> isinstance(_CALLBACK_CODE, str)
True

**Core callback logic is present**:

>>> "performUpdate" in _CALLBACK_CODE
True
>>> "source.change.emit()" in _CALLBACK_CODE
True

**Error handling** — fetch calls include ``.catch()``:

>>> ".catch(" in _CALLBACK_CODE
True

**Key data structures referenced in JS**:

>>> "metric_to_info" in _CALLBACK_CODE
True
>>> "metric_info_to_summary" in _CALLBACK_CODE
True
>>> "window._chimera_data" in _CALLBACK_CODE
True


Public function: ``save_metric_data_json``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Serializes the data dictionary and cascading maps to a JSON file that
the HTML plot loads at runtime.

>>> import json, tempfile, os
>>> from schedview.plot.maf_summary import save_metric_data_json
>>> tmpdir = tempfile.mkdtemp()
>>> json_path = os.path.join(tmpdir, "test_data.json")
>>> save_metric_data_json(summary_df, unique_metrics, json_path)

**Output is valid JSON with expected top-level keys**:

>>> with open(json_path) as f:
...     data = json.load(f)
>>> sorted(data.keys())
['data_dict', 'metric_info_to_summary', 'metric_to_info']

**Data dict keys use pipe-delimited format**:

>>> all("|" in k for k in data["data_dict"].keys())
True

**NaN values are serialized as JSON null** (not bare ``NaN``):

>>> import math
>>> df_nan = summary_df.copy()
>>> df_nan.loc[0, "summary_value"] = float("nan")
>>> nan_path = os.path.join(tmpdir, "nan_test.json")
>>> unique_nan = df_nan.drop_duplicates(
...     subset=["metric_name", "slicer_name",
...             "metric_info_label", "summary_metric"])
>>> save_metric_data_json(df_nan, unique_nan, nan_path)
>>> with open(nan_path) as f:
...     content = f.read()
>>> "NaN" not in content
True
>>> with open(nan_path) as f:
...     nan_data = json.load(f)
>>> nan_data["data_dict"]["fO|<none>|fOArea"]["summary_value"][0] is None
True

>>> import shutil
>>> shutil.rmtree(tmpdir)


Report: ``schedview.examples.summary_metric_plotter``
-----------------------------------------------------

This module provides the command-line executable that drives the full
workflow: collect → save JSON → plot → report HTML.

>>> from schedview.examples.summary_metric_plotter import (
...     make_summary_metric_plot, main)
>>> make_summary_metric_plot.__module__
'schedview.examples.summary_metric_plotter'

**Signature**:

>>> import inspect
>>> sig = inspect.signature(make_summary_metric_plot)
>>> sorted(sig.parameters.keys())
['build_date', 'db_path', 'output_html', 'run_name_pattern', 'title']
>>> sig.parameters['title'].default
'Summary Metric Explorer'
>>> sig.parameters['run_name_pattern'].default
'chimera_%'

**CLI entry point is a click command**:

>>> import click
>>> isinstance(main, click.Command)
True


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
- **Defensive parsing**: malformed run names are handled gracefully (logged
  and dropped), testable with a fixture DB containing bad rows.
- **Structural verification**: the Bokeh layout returned by
  ``make_metric_selector_plot`` can be inspected programmatically for
  expected widget types, renderer count, and legend structure.
- **JSON round-trip**: ``save_metric_data_json`` output can be verified by
  loading with ``json.load`` and checking structure and types.
- **Fixture-based integration tests**: all tests use in-memory SQLite
  fixture databases rather than hardcoded file paths.

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
- ``make_metric_selector_plot`` is decomposed into private helpers
  (``_create_metric_selectors``, ``_preallocate_sources_and_renderers``,
  ``_create_combined_legend``) to keep the main function under ~220 lines.
- The CustomJS callback is stored as a module-level constant
  (``_CALLBACK_CODE``) with a contract comment documenting the Python/JS
  interface, making it easy to locate and maintain.
- Fetch calls in the JavaScript include ``.catch()`` error handlers for
  user-visible feedback when the JSON data file is missing.
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
- ``re`` (standard library)
- ``logging`` (standard library)


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
   * - (inline date parsing in ``load_chimera_summary``)
     - ``schedview.collect.maf_summary``
     - ``_extract_transition_date`` (private)
   * - ``get_all_metric_data_dict``
     - ``schedview.plot.maf_summary``
     - ``_build_data_dict`` (private)
   * - ``make_metric_selector_plot``
     - ``schedview.plot.maf_summary``
     - ``make_metric_selector_plot``
   * - (inline widget creation in ``make_metric_selector_plot``)
     - ``schedview.plot.maf_summary``
     - ``_create_metric_selectors`` (private)
   * - (inline source allocation in ``make_metric_selector_plot``)
     - ``schedview.plot.maf_summary``
     - ``_preallocate_sources_and_renderers`` (private)
   * - (inline legend creation in ``make_metric_selector_plot``)
     - ``schedview.plot.maf_summary``
     - ``_create_combined_legend`` (private)
   * - (inline JS callback string in ``make_metric_selector_plot``)
     - ``schedview.plot.maf_summary``
     - ``_CALLBACK_CODE`` (module-level constant)
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
