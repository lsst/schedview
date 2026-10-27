API
===

.. toctree::
    :maxdepth: 4


Applications
------------

.. automodule:: schedview.app.prenight
    :members:
    :show-inheritance:

Summary Progress Commands
~~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`progress` for installed command syntax, embedded and external data
modes, the records schema, and the pending manual acceptance checklist.

.. automodule:: schedview.app.progress_explore

``make_summary_progress_data DB_PATH JSON_PATH``
    Collect and validate summary records from a local MAF database and write
    bare records JSON with epoch-millisecond calendar dates and null gaps.

``make_summary_progress_plot SUMMARY_METRICS PAGE_PATH``
    Write standalone HTML with embedded database records or an external JSON URL.
    Options: ``--input-kind auto|database|json-url`` and ``--title TEXT``.

The Python objects ``make_summary_progress_data`` and
``make_summary_progress_plot_cli`` in this module are Click commands, not the
DataFrame plotting function. Use ``--help`` for installed command usage; import
``schedview.plot.progress.make_summary_progress_plot`` for notebook plotting.

Collect
-------

.. automodule:: schedview.collect
    :members:
    :show-inheritance:

Summary Progress Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SummaryMetrics`` is a ``pandas.DataFrame`` type alias with the required
columns in ``SUMMARY_COLUMNS``. See :doc:`progress` for field types, run/label
grammars, date conventions, sequence invariants, and duplicate rules.

.. automodule:: schedview.collect.progress
    :members: load_summary_metrics, validate_summary_metrics

Compute
-------

.. automodule:: schedview.compute
    :members:
    :show-inheritance:

Plot
----

.. automodule:: schedview.plot
    :members:
    :show-inheritance:

Summary Progress Plotting
~~~~~~~~~~~~~~~~~~~~~~~~~

The summary interface accepts one validated DataFrame (including a filtered
copy) or an external JSON URL. It does not use the older paired-plot API's
baseline reference ray. See :doc:`progress` for notebook examples, selector
behavior, styles, gaps, ranges, and browser reload semantics.

.. automodule:: schedview.plot.progress
    :members: make_summary_progress_plot

Utilities
---------

.. automodule:: schedview.param
    :members: Series, DataFrame
    :show-inheritance:

.. automodule:: schedview.sphere
    :members: offset_sep_bear, rotate_cart
    :show-inheritance:
