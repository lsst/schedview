How the Summary Progress Callback Works
=======================================

The interactive summary progress plot (see :doc:`progress`) is built in
Python by ``schedview.plot.progress.make_summary_progress_plot``, but all of
its interactivity runs in the browser. A single JavaScript function, stored in
the Python string ``schedview.plot.progress._PROGRESS_CALLBACK``, loads the
records, updates the four selectors, rebuilds the plotted lines and points,
fits the axis ranges, rewrites the legends, and reports status.

This page explains how that callback works for readers who are comfortable with
Python but less familiar with JavaScript or with Bokeh's browser-side design.
The source itself is heavily commented and begins with a short guide to the
JavaScript syntax it uses; read it alongside this page.

Bokeh Background
----------------

Two halves: Bokeh and BokehJS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bokeh has two parts:

* The **Python library** (``bokeh``) builds a tree of *models*: figures,
  widgets, data sources, glyph renderers, ranges, callbacks, and so on. Python
  model objects only *describe* the visualization. They do not draw anything.
* **BokehJS** is a JavaScript library loaded by the web page (here, from the
  Bokeh CDN). It contains a JavaScript counterpart of every model class, and
  it does all rendering and event handling.

To display a visualization, Python serializes its models into a JSON
*document*. In standalone output (``bokeh.embed.file_html``, used by the
``make_summary_progress_plot`` command) and in notebook output
(``bokeh.plotting.show`` after ``output_notebook``), that JSON is written
directly into the HTML. BokehJS then reconstructs equivalent JavaScript model
objects from it and draws them.

.. mermaid::

   flowchart LR
       subgraph Python["Python, at page-generation time"]
           A["SummaryMetrics DataFrame<br/>or JSON URL"] --> B["make_summary_progress_plot"]
           B --> C["Bokeh models:<br/>Select / MultiSelect widgets,<br/>Div status and legends,<br/>ColumnDataSources, figure,<br/>CustomJS callback"]
       end
       C -- "serialized as JSON<br/>into HTML or notebook output" --> D
       subgraph Browser["Browser, after the page loads"]
           D["BokehJS rebuilds the<br/>same models in JavaScript"] --> E["Rendered plot and widgets"]
           D --> F["CustomJS callback runs<br/>on startup and on<br/>each selector change"]
           F -- "assigns new model<br/>property values" --> E
       end

After serialization, **no Python process is involved**. There is no Bokeh
server and no kernel communication. Everything the plot does in response to a
user's selection must therefore be done by JavaScript already present in the
page. This is why the same output works as a static HTML file on a web server
and in a notebook cell that is not re-executed.

Models and properties in the browser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every BokehJS model has the same properties as its Python counterpart, with
the same names. Assigning a new value to a property in JavaScript updates the
display automatically. For example, in the callback:

* ``status.text = "..."`` changes the text of a ``Div``.
* ``metric.options = [...]`` changes the choices of a ``Select`` widget, and
  ``metric.value = "..."`` changes its selection.
* ``lines.data = {...}`` replaces all columns of a ``ColumnDataSource``, and
  every glyph drawn from that source is redrawn.
* ``plot.x_range.start = ...`` moves the visible x limits.

Property assignments also emit *change events*. That matters here, because
the callback listens for changes to the selectors' ``value`` properties: when
the callback itself assigns ``source.value``, it triggers another invocation
of itself. See `Re-entrancy, busy flag, and selection key`_ below.

ColumnDataSource
~~~~~~~~~~~~~~~~

A ``ColumnDataSource`` holds data in *columns*: a mapping from column name to
an array, with all arrays the same length, like a dict of lists or a minimal
``pandas.DataFrame``. Glyph renderers refer to columns by name. For example,
``plot.scatter(x="date", y="summary_value", source=point_source)`` draws one
marker per row of ``point_source``.

The plot uses two sources:

``lines`` (drawn by ``plot.multi_line``)
   One *row per line sequence*. Its ``xs`` and ``ys`` columns hold a whole
   array of dates and values for each sequence, so ``multi_line`` can draw a
   variable number of lines from one source. ``color``, ``width``, ``alpha``,
   and ``dash`` give each line's style. A ``NaN`` in ``ys`` breaks a line,
   which is how missing measurements appear as gaps.

``points`` (drawn by ``plot.scatter`` and used by the hover tool)
   One *row per finite measurement*, with the record fields shown in hover
   text and the band ``color``.

The records themselves arrive as the opposite layout: a list of row objects,
one per summary record (the JSON ``orient="records"`` format). The callback
regroups rows into columns on every update.

CustomJS callbacks
~~~~~~~~~~~~~~~~~~

``bokeh.models.CustomJS`` is a model whose ``code`` property contains
JavaScript source text and whose ``args`` property maps names to Python
objects. Python never runs the code. The objects in ``args`` are serialized
with the document: Bokeh models become references to the corresponding
BokehJS models, and plain values (lists, dicts, strings, numbers, ``None``)
become JSON values.

The code can be a plain function body or, as here, an *ES module*: JavaScript
source that ``export``\ s a default function. BokehJS compiles the module in
the browser and calls the exported function as

.. code-block:: javascript

   callback(args, obj, data, context)

where ``args`` is the mapping from ``CustomJS(args=...)`` and ``obj`` is the
object that triggered the call. The progress callback uses only the first two
parameters and names them ``args`` and ``changed``. The function is declared
``async``, so it may ``await`` the browser's ``fetch`` while loading external
JSON, much like an ``asyncio`` coroutine.

A ``CustomJS`` model is attached to events in Python:

* ``widget.js_on_change("value", callback)`` runs the callback whenever the
  widget's ``value`` property changes, with the widget as ``obj``.
* ``model.js_on_event(DocumentReady, callback)`` runs it when BokehJS has
  finished building the document.

``CustomJS.execute`` is itself asynchronous: it waits for compilation (even
of an already compiled module) before calling the function. A callback
triggered by a property assignment therefore does not interrupt the code that
made the assignment; it runs later, after that code finishes or reaches an
``await``.

Documents, notebook outputs, and startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Bokeh *document* is the collection of models rendered together. In a
standalone page there is normally one document. In a notebook, each
``show(...)`` call produces a separate output with its own document, and
several of these can coexist on one notebook page.

Bokeh documents that, in standalone embedding, a JavaScript ``DocumentReady``
callback must be registered on a document, such as ``bokeh.io.curdoc()``,
rather than relying on a model alone. When Bokeh embeds models, it creates a
temporary ``Document`` and copies into it the document-level JavaScript event
callbacks of ``curdoc()``. ``make_summary_progress_plot`` uses this behavior:

1. Each plot's ``status`` ``Div`` is tagged with ``schedview-progress-startup``
   and given the progress callback as its own ``DocumentReady`` callback.
2. A single generic *dispatcher*, ``_PROGRESS_DOCUMENT_READY``, is registered
   once on ``curdoc()`` and is therefore copied into every embedded document.
3. When a document becomes ready, the dispatcher searches only that
   document's models for tagged ``status`` models and starts each one's
   callback without waiting for it, so a slow fetch for one plot cannot
   delay another.

Because the dispatcher receives no plot-specific arguments, a notebook output
only starts the plots it contains, never those belonging to another output.
Startup happens at document readiness, not when the figure first becomes
visible, so plots in initially hidden tabs are loaded before they are shown.

.. mermaid::

   sequenceDiagram
       participant Py as Python make_summary_progress_plot
       participant Doc as Embedded Bokeh document
       participant Disp as Startup dispatcher
       participant CB as Progress callback
       Py->>Doc: status Div tagged and given callback for DocumentReady
       Py->>Doc: dispatcher copied from curdoc()
       Note over Doc: Browser loads page, BokehJS builds models
       Doc->>Disp: DocumentReady(document)
       loop each tagged status model in this document
           Disp->>CB: execute(document), not awaited
       end
       Note over CB: changed is the document,<br/>so this is the startup call

Callback Arguments
------------------

``make_summary_progress_plot`` passes these entries in ``CustomJS(args=...)``;
the first statement of the callback unpacks them into local names.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Name
     - Contents
   * - ``metric``
     - ``Select`` widget. ``value`` is one metric-name string.
   * - ``source``, ``label``, ``summary``
     - ``MultiSelect`` widgets. ``value`` is a list of selected option values;
       ``options`` is the list of available choices.
   * - ``status``
     - ``Div`` displaying loading, count, gap, selection-limit, and error
       messages. It also stores the callback's persistent state.
   * - ``lines``, ``points``
     - The two ``ColumnDataSource`` models described above.
   * - ``plot``
     - The figure, whose title and ``x_range``/``y_range`` are updated.
   * - ``legends``
     - Three ``Div`` models for the source, band, and summary legends.
   * - ``records``
     - Embedded list of record objects, or ``null`` when data are external.
   * - ``url``
     - External JSON URL string, or ``null`` when records are embedded.
   * - ``colors``
     - Mapping of band to color from ``schedview.plot.colors.make_band_cmap``.
   * - ``styles``
     - Mapping of ``visit_source`` to ``[line width, alpha]``
       snapshotted for this plot: consdb and chimera use ``SOURCE_STYLES``;
       the configured reference tag uses the default baseline's style.
   * - ``dashes``
     - List of Bokeh's named ``LineDash`` styles. Its length is also the
       maximum number of summary metrics that can be selected at once.

Exactly one of ``records`` and ``url`` is non-null. Embedded records were
validated and serialized by Python when the plot was created. External JSON is
expected to follow the same records format; the callback reports fetch and
JSON-parsing failures but does not validate the records.

Persistent State
----------------

Like a Python function, the callback starts every invocation with fresh local
variables. Anything that must survive between invocations is kept in an object
stored as an ad hoc attribute of the plot's own ``status`` model,
``status._progress_state``. JavaScript objects accept new attributes freely,
much like instances of a plain Python class.

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Field
     - Purpose
   * - ``data``
     - Loaded records, or ``null`` before loading finishes.
   * - ``started``
     - Set at the beginning of the first call, so only one call loads data.
   * - ``busy``
     - True while an update is running; overlapping calls return immediately.
   * - ``slots``
     - ``Map`` from summary-metric name to index in ``dashes``, so each selected
       summary keeps its line style across updates.
   * - ``previousSummaries``
     - Summary selection after the last update, used to give existing choices
       priority when the user exceeds the selection cap.
   * - ``selection``
     - JSON string of all four selector values after the last update.
   * - ``bandMode``
     - Whether the third control used band options in the last update.
   * - ``labelRows``
     - Records matching Metric and Source in the last update, before label
       or summary filtering; used to translate label selections into bands.

The state is stored on the model, rather than in a module-level JavaScript
variable, for two reasons. BokehJS may compile the callback module more than
once on a page, and each compiled copy would get its own module-level
variables. Also, several independent plots can share a page, and each has its
own ``status`` model and therefore its own state.

Re-entrancy, Busy Flag, and Selection Key
-----------------------------------------

The callback is invoked:

* once at startup by the dispatcher, with ``changed`` set to the document;
* by the browser whenever the user changes a selector, with ``changed`` set to
  that selector; and
* indirectly by itself, because assigning a selector's ``value`` emits a
  change event that queues another invocation.

Three guards keep these invocations from interfering:

``started``
   Set before the first ``await``. A call arriving during the fetch sees that
   startup has been claimed, so it cannot start a second request.

``busy``
   Set for the duration of an update and cleared in ``finally``. Calls that
   arrive while an update is in progress, including during the fetch,
   return immediately.

``selection``
   In ``finally``, the callback records ``selectionKey()``, a JSON string of
   the four selector values it has settled on. The queued invocations caused by
   its own assignments then find an unchanged selection and return. Without
   this check, such calls would rebuild the plot again, resetting a user's
   manual zoom and possibly overriding an intentionally empty selection.

.. mermaid::

   sequenceDiagram
       participant U as User
       participant W as source MultiSelect
       participant CB as Progress callback
       participant S as status._progress_state
       U->>W: changes selection
       W->>CB: execute(source)
       CB->>S: selection key differs and busy false
       CB->>S: busy = true
       CB->>W: assigns options and value, which queues another call
       Note over CB: rebuild plot, ranges, legends, status
       CB->>S: selection = selectionKey(), busy = false
       W->>CB: queued execute(source)
       CB->>S: selection key unchanged
       Note over CB: returns without changes

Processing Steps
----------------

The body of the callback is divided into numbered steps, matching the
section comments in the source.

.. mermaid::

   flowchart TD
       G{"Selection unchanged<br/>since last update,<br/>or busy?"} -- yes --> R["return"]
       G -- no --> B["busy = true"]
       B --> S1["1. First call only:<br/>disable controls, then load<br/>embedded records or await fetch"]
       S1 --> S2["2. Cascade selector options<br/>metric to source to label/band to summary"]
       S2 --> S3["3. Enforce summary<br/>selection cap"]
       S3 --> S4["4. Assign dash-style<br/>slots to summaries"]
       S4 --> S5["5. Group selected records<br/>into line sequences"]
       S5 --> S6["6. Build line and point<br/>columns; replace source data"]
       S6 --> S7["7. Fit visible and Reset<br/>ranges to finite data"]
       S7 --> S8["8. Rebuild three<br/>HTML legends"]
       S8 --> S9["9. Write status message"]
       S1 -. "error in any step" .-> E["catch: clear data and legends,<br/>disable controls,<br/>show failure message"]
       S9 --> F["finally: remember selection,<br/>busy = false"]
       E --> F

Step 1: Load the records
~~~~~~~~~~~~~~~~~~~~~~~~

Only the first call loads data. It disables all four controls, then either
copies the embedded ``records`` or fetches ``url``. The fetch uses
``cache: "no-store"`` so that a page reload obtains the current file, and a
non-success HTTP status is turned into an error. Subsequent selection changes
reuse ``state.data``: external JSON is fetched once per page load, and a
replaced file is seen only after the page is reloaded.

A relative ``url`` is resolved by the browser against the URL of the page
containing the plot, not against any directory used when the page was
generated.

Step 2: Cascade selector options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The selectors form a cascade. Each one's options are distinct values found in
records matching all selections *upstream* of it. Metric, original-label,
and summary options are sorted. Source options put ``chimera`` first when
available, followed by the other available sources in sorted order. Band
options use the fixed order
``all``, ``u``, ``g``, ``r``, ``i``, ``z``, ``y``, skipping absent bands.
The shared embedded/external cascade applies source ordering on initial load,
metric changes, and external-data reloads without adding absent sources or
changing retained selections.
A working list, ``rows``, is narrowed after each control:

.. mermaid::

   flowchart LR
       D["all records"] -- "metric_name equals<br/>metric.value" --> M["rows"]
       M -- "options for source;<br/>keep visit_source<br/>in source.value" --> SO["rows"]
       SO -- "choose label or band mode;<br/>keep label key or band<br/>in label.value" --> L["rows"]
       L -- "options for summary;<br/>after cap and slots, keep<br/>summary_metric in summary.value" --> SU["rows to plot"]

Because each list is derived from records matching the union of upstream
choices, an option appears if *any* selected upstream combination has it.

Whether a control's selection is changed depends on why the callback ran:

* At startup, or when a control *upstream* of this one changed, the selection
  is reconciled. Previously selected values that are still available are
  kept; if none are, every available option is selected (up to the summary
  cap).
* Otherwise the selection is left exactly as the user made it. In particular,
  a user who clears a control sees an empty plot and a no-data message rather
  than having all options reselected.

The metric selector is single-valued and is set to the first sorted metric
only at startup. Source and summary use the shared ``cascade`` helper, which
also sets ``options`` and disables a control with no options. The third control,
still named ``label`` in the callback, is handled separately because it can
switch between original-label and band options.

Before filtering by that control or by summary, the callback examines every
record matching Metric and Source. The local ``standardLabel(row)`` helper
requires a supported ``row.band`` and exact, case-sensitive equality between
``row.metric_info_label`` and ``row.visit_source + "_" + row.band``. This uses
the actual source, including an alternate reference tag; a fallback
``band="all"`` alone does not make a custom label standard.

If there is at least one matching record and every label is standard, the
control's title becomes **Band**. Each option is a ``[band, band]`` pair,
and ``label.value`` holds plain band strings such as ``"g"``. Selecting a
band retains every record with that band across the selected sources.
``all`` means the literal ``<source>_all`` labels, not all available bands.

If any matching label is absent, custom, case-variant, or source-mismatched,
the title remains **Metric info label** and options retain original-label
identities. Empty upstream results also use label mode, with an empty,
disabled control. In original-label mode:

* Null and empty labels are the same logical label (``canonical`` maps both
  to ``""``).
* Each option value is ``JSON.stringify`` of the canonical label, for example
  ``'""'`` or ``'"chimera_g"'``. This prevents a real label from colliding with
  the representation of the empty label.
* Options are ``[value, display text]`` pairs. The empty label is displayed as
  ``(no label)``; other labels are displayed with their quotes, so a literal
  label ``(no label)`` remains distinguishable.

When the mode changes, selections are translated before the usual
retain-or-fallback reconciliation:

* From labels to bands, the callback finds selected standard labels in the
  previous ``state.labelRows`` and retains their bands if still available.
* From bands to labels, it selects all standard labels in the new upstream
  rows corresponding to the previously selected bands.

After reconciliation, ``state.bandMode`` and ``state.labelRows`` are updated,
and ``rows`` is filtered using either ``row.band`` or
``labelKey(row.metric_info_label)``. Clearing the third control itself remains
an empty selection; upstream changes use the normal fallback if no choices
survive. Every metric/source change reevaluates the mode, as does the first
load of embedded records or current external JSON after page reload.

This changes only selection: original labels remain in hover fields and in
the sequence keys used in step 5. For example, selecting ``g`` can show both
``consdb_g`` and ``comparison_g`` without merging their lines.

Step 3: Enforce the summary selection cap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each selected summary metric needs its own line style, so no more than
``dashes.length`` summaries can be selected. Automatic selections in step 2
are already capped. If the user's own selection exceeds the cap, the
summaries that were selected before (``state.previousSummaries``) are kept
first, then newly added ones, and the list is truncated to the cap. The
attempted excess is rejected and ``limited`` is set, so that step 9 explains
the limit. A full selection can still be changed by deselecting a summary
before selecting a replacement.

Step 4: Assign dash-style slots
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``state.slots`` maps summary names to indices into ``dashes``. It persists
between updates so that a summary's line style does not change merely because
another summary is added or removed.

.. mermaid::

   flowchart TD
       A["Delete slots of summaries<br/>no longer selected"] --> B{"Mean or Median<br/>selected?"}
       B -- yes --> C["Give Mean the solid slot<br/>and Median the dashed slot,<br/>removing any other occupant"]
       B -- no --> D
       C --> D["Give every selected summary<br/>without a slot the lowest<br/>unused slot index"]

``Mean`` and ``Median`` (exact, case-sensitive names) always use ``solid`` and
``dashed`` when selected. Any summary displaced from those slots is
reassigned in the final step; all other surviving summaries keep their
slots. Step 3 guarantees that a free slot exists.

Step 5: Group records into line sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The remaining ``rows`` are grouped into one sequence per combination of metric
name, canonical label, summary metric, and visit source. Each group becomes
one line. The group key is a JSON string of those four values; JSON encoding
avoids ambiguity if a label contains whatever character would otherwise be
used as a separator. The ``Map`` of groups is used like
``collections.defaultdict(list)``.

Different labels that share a band, and different sources of the same
summary, remain separate lines even when they share a color.

Step 6: Build line and point columns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For each group, the callback:

1. sorts its records by ``date`` (epoch milliseconds);
2. takes the line color from the band, width and alpha from the source, and
   dash from the summary's slot, using the group's first record, since all
   records in a group share those properties;
3. appends one entry to each ``lines`` column: arrays of dates and values,
   with ``NaN`` for missing or non-finite measurements, plus the style values;
4. appends one ``points`` row for each finite measurement.

Consecutive recorded dates are connected regardless of spacing. No rows are
synthesized for absent dates; only explicit missing or non-finite values break
a line. Points keep isolated measurements visible.

Both sources are then replaced in two assignments, ``lines.data = ...`` and
``points.data = ...``, after all new columns have been built, rather than
being modified piece by piece.

Step 7: Fit the axis ranges
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``extent`` helper computes each axis's ``[start, end]`` from the finite
points only:

* Normal spans get 5 percent padding at each end.
* If all values are equal, a single date is padded by one day, and a constant
  value by ``max(abs(value) * 0.05, 1)``.
* With no finite points, fixed fallback ranges are used.

Both the visible bounds (``start``/``end``) and the Reset tool's bounds
(``reset_start``/``reset_end``) are set, so Reset returns to the current
selection's limits rather than to those of the initial selection. Because
ranges are set only during a real update, manual pan and zoom persist until
the next selection change.

Step 8: Rebuild the legends
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The three legends are ordinary ``Div`` models filled with HTML. Each entry is a
small inline SVG line drawn by ``swatch`` with the same color, width, alpha,
and dash as the plotted lines; ``dashArrays`` translates Bokeh dash names into
SVG ``stroke-dasharray`` values. Using HTML rather than Bokeh legends means
the legends add no data to the plot's ranges and cannot hide individual
series independently of the selectors.

Labels, names, and URLs inserted into HTML are passed through ``escape``,
which serves the same purpose as Python's ``html.escape``.

Step 9: Status message
~~~~~~~~~~~~~~~~~~~~~~

The ``status`` ``Div`` reports, in order: a selection-limit message if step 3
rejected an addition; the number of finite measurements, or a no-data message;
the number of missing or non-finite measurements shown as gaps; a reminder of
the summary cap when more summaries exist than can be selected; and, for
external data, the URL.

Error handling
~~~~~~~~~~~~~~

Any exception, such as a network failure, HTTP error status, or invalid JSON,
is handled in ``catch``. The callback clears both data sources and the legends,
disables the controls, and shows
``Failed to load <source>: <message>`` in the status area. The plot never
continues to display old data as though it had loaded successfully.

The ``finally`` block always runs, whether the update succeeded, failed, or
returned early. It records the settled selection key and clears ``busy``.

Testing
-------

The browser-free API story checks representative invalid inputs and serialization
of populated and empty plots, but cannot execute the callback. Representative
callback behavior is covered by the opt-in
Playwright browser tests in ``tests/test_plot_progress.py``, which run only
when ``ENABLE_PLAYWRIGHT_TESTS=1`` is set (see :doc:`playwright_testing`).
After changing ``_PROGRESS_CALLBACK``, run those browser tests, not only the
default test suite.

The main exploration story checks cascading selections, summary clearing and
restoration, an explicit gap with irregular dates, and Reset after switching
metrics. ``test_user_selects_bands_across_sources_and_returns_to_original_labels``
checks cross-source g-band selection, literal ``all``, separate series, and
translation between Band and original-label modes. The summary-limit story
checks Mean/Median preferred dashes after replacing selected summaries.

The external-data story checks page-relative URLs, reload-only updates, mode
reevaluation, and visible fetch failure. Separate notebook outputs retain
independent selections; the dashboard story combines initially hidden plots
with a pending fetch to check independent startup and interaction after reveal.

These stories are deliberately representative, not exhaustive. They do not
assert Source or Band option ordering, Band clearing, empty upstream controls,
or legend contents. Those behaviors remain part of the documented interface;
removing their automated assertions does not change the product requirements.
