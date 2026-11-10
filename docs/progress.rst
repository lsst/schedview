Summary Progress
================

Plot scalar MAF summary metrics against observing-night dates, either in a
notebook or in a standalone HTML page. Inputs may contain snapshot measurements
from completed visits (``consdb``), reference-simulation snapshots (``baseline``
by default), chimera
extrapolations (``chimera``), or a combination. A chimera combines completed
visits up to a transition night with baseline simulation visits thereafter.
Only supplied records are plotted: this interface adds neither target values
nor a constant final-baseline reference. Bespoke simulations are out of scope.

The collection, plotting, and reporting stages live in
``schedview.collect.progress``, ``schedview.plot.progress``, and
``schedview.app.progress_explore``, respectively. Use an installed ``schedview``
environment with the latest current Bokeh release. Standalone plots use browser
callbacks and do not require a Bokeh server. See :doc:`progress_callback` for
how the browser callback works.

Notebook API
------------

Load one DataFrame and pass it directly to the plot function:

.. code-block:: python

   from bokeh.io import output_notebook
   from bokeh.plotting import show
   from schedview.collect.progress import load_summary_metrics
   from schedview.plot.progress import make_summary_progress_plot

   output_notebook()
   summary_df = load_summary_metrics("/path/to/resultsDb_sqlite.db")
   show(make_summary_progress_plot(summary_df))

Replace the example path with your MAF results database. Relative paths resolve
against the notebook's working directory. No particular workspace layout or
bundled representative database is required.

To compare against a different simulation, pass the same explicit tag through
collection, validation, and plotting:

.. code-block:: python

   from schedview.collect.progress import validate_summary_metrics

   comparison_df = load_summary_metrics(
       "/path/to/resultsDb_sqlite.db", reference_sim_tag="comparison"
   )
   validate_summary_metrics(comparison_df, reference_sim_tag="comparison")
   show(make_summary_progress_plot(comparison_df, reference_sim_tag="comparison"))

The keyword-only ``reference_sim_tag="baseline"`` selects exactly one reference.
An alternate replaces baseline, rather than adding an alias. Tags are literal,
case-sensitive, nonempty strings, distinct from the reserved ``consdb`` and
``chimera`` names. Actual source names remain in records, selectors, and legends;
reference styling follows the role. There is no mutable module-level setting,
automatic inference, or support for multiple reference simulations. Each plot
snapshots its configuration, so independent notebook plots can use different tags.

Filtered copies are valid inputs; retain all required columns and consistent
derived values. There is no second, separately maintained selector DataFrame:

.. code-block:: python

   from schedview.collect.progress import validate_summary_metrics

   filtered_df = summary_df.loc[summary_df["band"].isin(["g", "r"])].copy()
   validate_summary_metrics(filtered_df)
   show(make_summary_progress_plot(filtered_df))

Restrict the supplied records to obtain the separate views:

.. code-block:: python

   chimera_df = summary_df.loc[summary_df["visit_source"] == "chimera"].copy()
   snapshot_df = summary_df.loc[
       summary_df["visit_source"].isin(["consdb", "baseline"])
   ].copy()
   show(make_summary_progress_plot(chimera_df))
   show(make_summary_progress_plot(snapshot_df))

``make_summary_progress_plot(summary_metrics, *, reference_sim_tag="baseline")`` returns a
``bokeh.models.UIElement`` with selectors, status, figure, and legends.
A DataFrame embeds its records. A string is always an external JSON URL in
the Python API, even if it looks like a local database path. It is not read
by Python. For example, ``make_summary_progress_plot("./progress_data.json")``
fetches from the browser's page context; notebook deployments must make that
URL accessible from the notebook page, not merely from the kernel filesystem.

``SummaryMetrics`` is a type alias for ``pandas.DataFrame``, not a wrapper.
``load_summary_metrics(db_path, *, reference_sim_tag="baseline") -> SummaryMetrics`` opens a MAF
SQLite results database read-only, joins ``metrics`` and ``summarystats`` on
``metric_id``, derives source/band/date fields, removes identical reruns,
validates, and returns deterministically ordered records.
Collected ``metric_id``, ``stat_id``, and ``dayobs`` columns use ``int64``;
``summary_value`` uses ``float64``, with SQL NULL measurements represented by
NaN and signed infinities preserved. These dtypes also apply to empty results.
Conversion follows validation and duplicate comparison; original labels and
constraints retain their strings or SQL NULL values.
``validate_summary_metrics(summary_metrics, *, reference_sim_tag="baseline", allow_duplicates=False) -> None``
validates without
mutating, sorting, or removing duplicates. It accepts filtered copies with
arbitrary indices and harmless extra columns, and rejects duplicate records
in caller-created frames, even if their values agree. Empty frames must still
contain every required column. Plotting validates DataFrame inputs; reporting
validates again before JSON export.
Use ``allow_duplicates=True`` only to validate equal reruns before deduplication;
conflicting measurements remain invalid, and the function never removes rows.

Installed Commands
------------------

Both commands take two positional arguments. Activate the installed environment
before running them, or use ``uv run --no-sync`` in the configured workspace.
Both accept ``--reference-sim-tag TAG`` (default ``baseline``). Use the same tag
for JSON export and embedded or external HTML generation. Invalid tags produce
contextual errors, including for empty data or external URLs.

Embedded HTML
~~~~~~~~~~~~~

.. code-block:: sh

   make_summary_progress_plot resultsDb.db /path/to/served/pages/progress_summary.html

The local SQLite database is read at page-generation time. Metric data are
embedded in the HTML; no companion JSON is created or required. Self-contained
here means embedded metric data, not completely offline operation: Bokeh
resources use the CDN and need not be inlined. Regenerate the HTML to update
embedded records.

External JSON and Reload
~~~~~~~~~~~~~~~~~~~~~~~~

Generate a data file independently, then a page that refers to it:

.. code-block:: sh

   make_summary_progress_data resultsDb.db /path/to/served/pages/progress_summary_data.json
   make_summary_progress_plot "./progress_summary_data.json" /path/to/served/pages/progress_summary.html

After the database changes, replace only the JSON:

.. code-block:: sh

   make_summary_progress_data resultsDb.db /path/to/served/pages/progress_summary_data.json

For an alternate reference, include its tag on both initial commands and every
subsequent JSON export:

.. code-block:: sh

   make_summary_progress_data --reference-sim-tag comparison resultsDb.db /path/to/served/pages/data.json
   make_summary_progress_plot --reference-sim-tag comparison "./data.json" /path/to/served/pages/figure.html

External JSON must use the reference tag configured in its HTML. JSON-only
updates may add records from ``consdb``, ``chimera``, and that reference tag;
changing the reference tag requires regenerating HTML. No configuration metadata
is added to the bare records array, and JavaScript does not validate tag agreement.

Serve the HTML and JSON over HTTP(S). ``./progress_summary_data.json`` resolves
relative to the served page URL, not the shell's working directory or Python's
filesystem. For a page at ``https://example.org/reports/progress_summary.html``,
it refers to ``https://example.org/reports/progress_summary_data.json``.
A root-relative URL such as ``/data/progress.json`` resolves at the page's origin.
Cross-origin JSON needs appropriate CORS permission from the data host.
Arbitrary ``file://`` browser fetch is not supported or promised; supplying a
local JSON path does not silently embed its contents. No HTTP server
implementation is included in this feature.
The hosting page must permit Bokeh resources and its browser callback/custom-model
execution under its Content Security Policy. Local browser verification does not
establish compatibility with the USDF notebook portal's deployment policy.

The browser fetches once per page load with ``cache: "no-store"``. Selecting
metrics uses the already loaded records; there is no polling, manual refresh
control, or automatic update of an open page. On browser reload, current JSON
rebuilds selectors, series, legends, and ranges, including newly added metrics,
sources, labels, summaries, and dates, without regenerating HTML. Data
initialization begins at Bokeh document readiness, not when the figure
first obtains a visible width. Plots in initially inactive tabs load before
being revealed; revealing or resizing them does not refetch data or reset
selections or manual zoom. A document-local dispatcher starts each plot
independently and only initializes plots belonging to that output, including
when a notebook renders separate outputs.
Loading and
source-specific fetch/HTTP/JSON-parsing errors appear near the plot. Failed
loads clear the plot rather than presenting old data as refreshed.

Input-Kind Grammar
~~~~~~~~~~~~~~~~~~

The plot command accepts
``make_summary_progress_plot SUMMARY_METRICS PAGE_PATH`` with optional
``--input-kind auto|database|json-url`` (default ``auto``) and
``--title TEXT`` (also ``-t TEXT``).

In ``auto`` mode, classification precedes filesystem access:

* An input with an HTTP or HTTPS scheme, case-insensitively, is an external URL,
  regardless of its suffix.
* A scheme-less input whose URL path component ends in ``.json``,
  case-insensitively, is external. Query strings and fragments do not affect
  that suffix check, so ``./progress.json?release=latest`` is external.
* Other inputs are treated as local SQLite paths. This does not imply support
  for other URL schemes such as ``ftp:`` or ``file:``.

External strings are passed through unchanged; the command does not check that
they exist locally or are reachable at generation time. Use an explicit mode
for ambiguous names or suffixless endpoints:

.. code-block:: sh

   make_summary_progress_plot --input-kind database results.json progress.html
   make_summary_progress_plot --input-kind json-url "./current_metrics" progress.html
   make_summary_progress_plot "https://example.org/api/metrics" progress.html

``database`` forces a local database read; ``json-url`` forces browser fetch.
The data command always reads a local database and writes JSON:
``make_summary_progress_data DB_PATH JSON_PATH``. Unreadable inputs, missing
schema, invalid records, and output failures produce contextual errors and
nonzero CLI exit codes. Browser fetch failures happen later and cannot be
reported as generation-time CLI failures.
Both commands refuse to overwrite their input database, including when the
output names a symbolic-link or hard-link alias of that database.
The HTML command also protects page-relative JSON paths and aliases from being
overwritten by its output, resolving those paths beside the output page and
ignoring URL queries/fragments for the collision check. It does not read JSON
contents or check remote URLs for availability.

Records and Validation
----------------------

Required DataFrame and JSON fields are:

.. list-table:: SummaryMetrics Schema
   :header-rows: 1
   :widths: 22 25 53

   * - Field
     - Python / JSON Value
     - Meaning
   * - ``metric_id``
     - Integer / number
     - Parent metric-bundle identifier, retained for provenance.
   * - ``stat_id``
     - Integer / number
     - Summary-row identifier and deterministic rerun ordering.
   * - ``run_name``
     - String
     - Original supported source and date identity.
   * - ``metric_name``
     - String
     - Base MAF metric name.
   * - ``slicer_name``
     - String
     - Original slicer identity.
   * - ``sql_constraint``
     - String or null
     - Original bundle constraint; normally blank for progress batches.
   * - ``metric_info_label``
     - String or null
     - Original subset/context label, not necessarily a band encoding.
   * - ``summary_metric``
     - String
     - Alias of ``summarystats.summary_name``.
   * - ``summary_value``
     - Real scalar or missing / number or null
     - Measurement; missing and non-finite values are gaps, never zero.
   * - ``visit_source``
     - String
     - ``consdb``, ``chimera``, or the configured reference tag, derived from ``run_name``.
   * - ``dayobs``
     - Integer / number
     - ``YYYYMMDD`` snapshot cutoff or chimera transition-night label.
   * - ``band``
     - String
     - ``u``, ``g``, ``r``, ``i``, ``z``, ``y``, or ``all``.
   * - ``date``
     - Timezone-naive pandas datetime / number
     - Calendar midnight of ``dayobs``; JSON uses epoch milliseconds.

Run and Label Grammars
~~~~~~~~~~~~~~~~~~~~~~

Supported run names match exactly and case-sensitively
``<source>_YYYYMMDD`` with exactly eight ASCII digits and no suffix. The source
is ``chimera``, ``consdb``, or the literal configured ``reference_sim_tag``
(``baseline`` by default). Collection excludes
unsupported names, including nulls, case variants, suffixes, and near misses,
and issues a warning counting excluded joined summary records. It does not
validate their other fields. An exact-format run with an impossible calendar
date is fatal and identifies the offending run and date: ``chimera_2026023``
is excluded, whereas ``chimera_20260230`` fails. Caller-created DataFrames
must contain supported, valid run names rather than expecting the plot to
filter them.
With an alternate reference tag, baseline runs are unsupported and excluded
without validating their dates or other fields. Caller-created baseline frames
instead fail validation under that tag, even if loaded with default settings.

A standard label matches exactly and case-sensitively
``<source>_<u|g|r|i|z|y|all>`` using one of the supported source prefixes, and it must agree
with the run. Otherwise ``band`` is ``all``. For example, ``chimera_g`` on a
chimera run maps to ``g``; ``Chimera_g``, ``chimera_G``, ``consdb_g`` on a
chimera run, unknown labels, and absent labels map to ``all``. The original
``metric_info_label`` is retained, and ``visit_source`` always comes from the
run, never the label.

Sequences and Duplicates
~~~~~~~~~~~~~~~~~~~~~~~~

A logical sequence is identified by
``(metric_name, summary_metric, metric_info_label)``. Null and empty values
are equivalent for grouping, without rewriting original labels or constraints.
Each sequence must have one ``slicer_name`` and one ``sql_constraint`` across
all dates and sources, not just within a run.

Records are unique by
``(run_name, metric_name, metric_info_label, summary_metric)``. Collection
compares duplicate values before JSON normalization:

* Finite measurements match only by exact equality, not a tolerance.
* Missing/NaN matches missing/NaN.
* Positive infinity matches positive infinity; negative infinity matches
  negative infinity.
* Unequal finite values or different finite/missing/signed-infinity categories
  conflict and fail.

Identical reruns collapse to the row with the highest ``stat_id``, including
its associated provenance. Retained missing/non-finite measurements stay in
the collected DataFrame and are counted in a warning. Validation errors name
the relevant record or sequence; ``validate_summary_metrics`` itself issues
no warnings and does not deduplicate caller-created frames.
Plot construction separately warns with counts of missing/non-finite values,
including for caller-created frames. Loading and plotting can therefore each
report their own gap counts. Browser status counts gaps in the current selection.

Date Convention
~~~~~~~~~~~~~~~

``dayobs`` is the observing-night date in UTC-12 under SITCOMTN-032, unchanged
during a Rubin observing night. It is a calendar label, not an elapsed-time
integer: convert it to a date before taking differences or adding days.
``date`` is derived using ``schedview.dayobs.DayObs`` and represents that same
calendar label at nominal, timezone-naive midnight. It is not the physical
UTC-12 start instant (12:00 UTC).
Supported observing dates have years from 2025 through 2050 inclusive. Behavior
outside that interval is unspecified; broader calendar support is not promised.

JSON encodes that nominal midnight in epoch milliseconds for Bokeh. For
example, ``dayobs=20260101`` has ``date=1767225600000``, corresponding to the
unchanged calendar label ``2026-01-01`` at nominal midnight. Interpret this
coordinate with UTC/calendar-label formatting, not conversion to a browser's
local timezone. Host or browser timezone must not shift the displayed night.

JSON Rules
~~~~~~~~~~

The interchange file is a bare records array, not an object containing records
and selector mappings. Reporting writes the equivalent of
``DataFrame.to_json(orient="records", date_format="epoch", date_unit="ms", double_precision=15)``
after validation and normalization of measurements on a copy. Missing/NaN and
both infinities become JSON ``null`` only after duplicate comparisons; finite
scalars use pandas' maximum supported precision of 15 decimal places. Do not
emit nonstandard ``NaN`` or ``Infinity`` literals.

Preserve all documented fields and types. Harmless extra fields are allowed
and ignored by the plot; there is no version field or version-failure contract.
Selectors are derived from the actual records. The browser parses JSON and
checks fetch failures but does not validate the schema, dates, or sequence
invariants. Produce external data through the validated Python pipeline rather
than relying on browser callbacks to diagnose hand-edited invalid records.

Interaction and Appearance
--------------------------

Controls appear above the plot in this order: single metric, multiple sources,
multiple original metric-info labels, multiple summary metrics. Bands are
selected indirectly through labels; there is no separate band selector.
Initially the first sorted metric is selected, followed by all available
downstream values within the summary-style cap.

Options cascade from metric to source to label to summary. Each downstream
list is the union of values in records matching all upstream selections, not
an intersection across sources or labels. Valid prior selections are retained;
if none survive an upstream change, all available options are selected in
sorted order within the cap. Intentionally clearing a multi-selection means
show nothing, with visible no-data status, not an automatic reset to all.
Missing/empty labels have a readable no-label option; nonempty labels are quoted
in the selector so literal text resembling the no-label option is distinguishable.
Hover retains the original label.

Every summary option remains available, but simultaneous selection is capped
at the number of named styles in Bokeh's ``LineDash`` enumeration. A visible
limit message explains how to deselect and replace summaries. A summary keeps
its dash slot while selected; freed slots can be reused. The exceptions are
``Mean`` and ``Median``, which always use solid and dashed lines respectively
when selected. Adding either reassigns any summary occupying its required slot;
other surviving summaries retain their styles. The cap applies to
selected summaries, not to the number of records or series.

Each ``(metric_name, metric_info_label, summary_metric, visit_source)`` group
is a separate date-sorted line. Distinct original labels sharing a band remain
separate lines, except the documented null/empty equivalence. Consecutive
recorded finite snapshots connect even at irregular intervals. Only explicit
missing/non-finite measurements break lines; absent dates are not synthesized.
Visible points keep isolated dates interpretable.

.. list-table:: Source Line Styles
   :header-rows: 1

   * - Source
     - Width
     - Alpha
   * - ``consdb``
     - 1
     - 1.0
   * - ``chimera``
     - 3
     - 0.6
   * - Configured reference tag (default ``baseline``)
     - 5
     - 0.3

Band colors come from ``schedview.plot.colors.make_band_cmap`` with all six
bands followed by ``all``, so ``all`` uses the helper's next assigned color.
Summary metrics use distinct named dash styles. Points have size 8 and alpha
0.6, with fully opaque black hover styling. Hover reports ``run_name``,
``metric_name``, original ``metric_info_label``, ``summary_metric``, and
``summary_value``. Three informational legends below, outside the axes explain
source thickness/alpha, band color, and summary dash. They do not support
click-to-hide and introduce no reference data.

Selection changes recompute ranges from selected finite measurements. Normal
ranges have 5 percent padding; a single date gets one day on either side and
a constant scalar gets ``max(abs(value) * 0.05, 1)`` padding. Calendar-aware
automatic ticks label the date axis. The plot uses Bokeh's standard linear
scale, without custom-model compilation or a Node.js requirement. Rendering
scalar spans or padded bounds that overflow JavaScript floating-point arithmetic
is not supported; measurements are not clamped or rescaled.
Reset restores the current selection's limits, not the original dataset's
limits. Manual pan/zoom persists only
between selection changes. Empty inputs or selections with no finite values
show no-data status and appropriate empty or disabled controls. Loading,
no-data, selection-limit, and source-specific error status are visible near
the plot rather than only in the browser console.
