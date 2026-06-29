============================================================
Design: Per-night statistics in ``schedview.reports``
============================================================

Overview
--------

This design extends the two public functions in ``schedview.reports`` —
``make_report_link_table`` and ``make_report_rss_feed`` — so they can
optionally display per-night observing statistics alongside the links to
static reports.

When a ``visits`` DataFrame is provided:

- ``make_report_link_table`` appends summary columns (visit count, science
  count, night hours, median FWHM, normalized effective time) to the HTML
  table, populated only for ``lsstcam`` rows.
- ``make_report_rss_feed`` populates the ``<description>`` element of
  ``lsstcam`` ``nightsum`` items with a formatted summary string containing
  total visits, science visits, seeing, effective-time metrics, and science
  targets.

When a ``prenight_visits`` DataFrame is provided:

- ``make_report_rss_feed`` populates the ``<description>`` element of
  ``lsstcam`` ``prenight`` items with the same formatted summary string, but
  computed from the **prenight simulation** of the night rather than from
  completed visits.  A prenight night with no matching simulation visits gets
  a completely blank description (unlike ``nightsum``, which falls back to
  ``"No visits on this night"``).

Additionally, numeric presentation is improved: float columns are rounded
to 2 decimal places and NaN/None values are rendered as empty strings.

Module Location
---------------

::

    schedview/reports.py

No new public functions are introduced.  The existing ``find_reports``,
``make_report_link_table``, and ``make_report_rss_feed`` remain the public
API.


New Module-Level Constants
--------------------------

``RSS_DESC_FORMAT``
    A format string template used to populate RSS item descriptions for
    ``lsstcam`` ``nightsum`` entries.  Contains placeholders for: ``total``,
    ``science``, ``fwhm``, ``mean_norm_teff``, ``visit_rate``, ``teff_rate``,
    ``targets``.

``INT_SUMMARY_COLUMNS``
    A list of column names from ``compute_tinysum`` output that should be
    displayed as integers in the link table: ``["Total", "science"]``.

``FLOAT_SUMMARY_COLUMNS``
    A list of column names from ``compute_tinysum`` output that should be
    displayed as rounded floats: ``["night_hours", "median FWHM",
    "total eff_time/exp_time"]``.

``SUMMARY_COLUMNS``
    The concatenation of ``INT_SUMMARY_COLUMNS + FLOAT_SUMMARY_COLUMNS``,
    defining the full set of summary columns added to the link table.


Function: ``make_report_link_table``
------------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def make_report_link_table(
        reports: pd.DataFrame,
        report_columns=("prenight", "multiprenight", "nightsum", "compareprenight"),
        visits: pd.DataFrame | None = None,
    ) -> str:

Parameters
~~~~~~~~~~

``reports`` : ``pd.DataFrame``
    A DataFrame of report metadata, as returned by ``find_reports``.

``report_columns`` : ``tuple``
    Names of reports to include as columns.

``visits`` : ``pd.DataFrame`` or ``None``
    A visits DataFrame (as from ``cached_read_visits``).  If provided,
    per-night summary columns are computed and appended to the table.
    Only ``lsstcam`` rows are populated; other instruments receive blank
    cells.  Defaults to ``None``.

Returns
~~~~~~~

``str``
    An HTML ``<table>`` element (parseable as XML) with report links and,
    optionally, summary statistics.

Implementation Steps
~~~~~~~~~~~~~~~~~~~~

1. **Pivot** the reports DataFrame to create a table with
   ``(night, instrument)`` as the index and report types as columns,
   containing HTML links.

2. **Compute tinysum** (only if ``visits`` is not ``None``):

   a. Instantiate an ``Almanac``.
   b. Call ``compute_tinysum(visits, almanac=almanac)`` and select only
      ``SUMMARY_COLUMNS``.
   c. Convert the ``dayObs`` integer index to ``datetime.date`` objects
      to align with the report table's ``night`` index level.

3. **Join summary onto link table**:

   a. Build a boolean mask identifying ``lsstcam`` rows.
   b. Reindex the tinysum DataFrame to match the full report_links index
      (using the ``night`` level), so that non-lsstcam rows and nights
      without visits receive ``NA``.
   c. Blank out non-lsstcam rows by assigning ``None``.
   d. Assign each summary column into the report_links DataFrame.

4. **Format for display**:

   a. Round float columns (``FLOAT_SUMMARY_COLUMNS``) to 2 decimal places.
   b. Cast all summary columns to ``object`` dtype so that
      ``fillna("")`` works uniformly across ``Int64``, ``Float64``, etc.
   c. Call ``fillna("")`` to replace any remaining NA values with empty
      strings.

5. **Render** with ``report_links.to_html(escape=False)``.


**Without visits — produces valid HTML table:**

>>> import datetime
>>> import xml.etree.ElementTree as ET
>>> import pandas as pd
>>> from schedview.reports import make_report_link_table

>>> reports = pd.DataFrame([
...     {"night": datetime.date(2025, 6, 20), "dayobs": "20250620",
...      "report": "nightsum", "instrument": "lsstcam",
...      "url": "http://example.com/ns", "link": '<a href="#">nightsum</a>',
...      "report_time": "2025-06-21T00:00:00+00:00", "fname": "ns.html"},
... ]).set_index(["instrument", "dayobs"]).sort_values("night", ascending=False)
>>> html = make_report_link_table(reports)
>>> root = ET.fromstring(html)
>>> root.tag
'table'

**With visits — summary columns appear in HTML output:**

>>> import numpy as np
>>> rng = np.random.default_rng(42)
>>> n = 20
>>> visits = pd.DataFrame({
...     "dayObs": np.full(n, 20250620),
...     "observationId": np.arange(n),
...     "seeingFwhmGeom": rng.uniform(0.6, 1.5, size=n),
...     "eff_time_median": rng.uniform(20.0, 40.0, size=n),
...     "exp_time": rng.uniform(25.0, 35.0, size=n),
...     "band": rng.choice(list("ugrizy"), size=n),
...     "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
...     "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
... })
>>> html = make_report_link_table(reports, visits=visits)
>>> "Total" in html
True
>>> "science" in html
True
>>> root = ET.fromstring(html)
>>> root.tag
'table'

**Non-lsstcam rows do not receive summary values:**

>>> reports2 = pd.DataFrame([
...     {"night": datetime.date(2025, 6, 20), "dayobs": "20250620",
...      "report": "nightsum", "instrument": "lsstcam",
...      "url": "http://x.com/a", "link": '<a href="#">nightsum</a>',
...      "report_time": "2025-06-21T00:00:00+00:00", "fname": "a.html"},
...     {"night": datetime.date(2025, 6, 20), "dayobs": "20250620",
...      "report": "nightsum", "instrument": "auxtel",
...      "url": "http://x.com/b", "link": '<a href="#">nightsum</a>',
...      "report_time": "2025-06-21T00:00:00+00:00", "fname": "b.html"},
... ]).set_index(["instrument", "dayobs"]).sort_values("night", ascending=False)
>>> html = make_report_link_table(reports2, visits=visits)
>>> root = ET.fromstring(html)
>>> root.tag
'table'


Function: ``make_report_rss_feed``
----------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def make_report_rss_feed(
        reports: pd.DataFrame,
        fname: str | None = None,
        max_days: int = 7,
        visits: pd.DataFrame | None = None,
        title: str = "schedview reports",
        description: str = "Statically generated reports on Rubin Observatory/LSST scheduler status and progress",
        prenight_visits: pd.DataFrame | None = None,
    ) -> ET.ElementTree:

Parameters
~~~~~~~~~~

``reports`` : ``pd.DataFrame``
    A DataFrame of report metadata, as returned by ``find_reports``.

``fname`` : ``str`` or ``None``
    File path to write the RSS XML.  ``None`` to skip writing.

``max_days`` : ``int``
    Maximum age of reports to include (in days from today).

``visits`` : ``pd.DataFrame`` or ``None``
    A visits DataFrame.  If provided, lsstcam nightsum items receive a
    formatted summary description.

``title`` : ``str``
    The ``<title>`` text for the RSS channel.

``description`` : ``str``
    The ``<description>`` text for the RSS channel.

``prenight_visits`` : ``pd.DataFrame`` or ``None``
    A visits DataFrame for the **prenight simulation** of the night.  If
    provided, lsstcam ``prenight`` items receive a formatted summary
    description computed from these visits.  These simulation visits carry the
    columns ``t_eff`` and ``visitExposureTime`` (rather than
    ``eff_time_median``/``exp_time``); those names are passed through to
    ``compute_tinysum`` via its ``eff_time_column``/``exp_time_column``
    parameters, so the visits should be supplied **unmodified**.  All prenight
    visits are counted as science (via ``all_science=True``), since the
    simulator only simulates science visits.  See "Obtaining prenight visits"
    below.

Returns
~~~~~~~

``ET.ElementTree``
    The RSS XML tree.

Implementation Steps
~~~~~~~~~~~~~~~~~~~~

1. **Compute tinysum** (only if ``visits`` is not ``None``): instantiate
   ``Almanac`` and call ``compute_tinysum`` on ``visits`` (the nightsum
   summary).  If ``prenight_visits`` is not ``None``, also call
   ``compute_tinysum`` on it, passing ``eff_time_column="t_eff"``,
   ``exp_time_column="visitExposureTime"``, and ``all_science=True`` (the
   prenight summary; the simulator only simulates science visits, so all of
   them count as science).  A single ``Almanac`` instance is shared.

2. **Build RSS skeleton**: Create ``<rss>`` root with ``version="2.0"``,
   add ``<channel>`` with ``<title>`` and ``<description>`` elements using
   the provided parameter values.

3. **Iterate** over reports rows.  Skip items older than ``max_days``.

4. **Per item**:

   a. Create ``<item>`` with ``<title>`` =
      ``"{report} for {instrument} on {night}"``.
   b. **Description logic** (the formatting of a populated description is
      factored into the private helper ``_format_summary_desc``, shared by the
      nightsum and prenight branches):

      - If ``instrument == "lsstcam"`` and ``report == "nightsum"`` and the
        nightsum tinysum is available: format the summary when the dayobs is
        in its index, else ``"No visits on this night"``.
      - If ``instrument == "lsstcam"`` and ``report == "prenight"`` and the
        prenight tinysum is available: format the summary when the dayobs is
        in its index, else an **empty string** (no fallback text).
      - Otherwise: empty string.

   c. Add ``<link>``, ``<guid>``, ``<category>``, and ``<pubDate>``
      elements.

5. **Indent** the XML tree and optionally write to file.


Obtaining prenight visits (caller responsibility)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``make_report_rss_feed`` does **not** fetch prenight-simulation visits itself;
it only formats whatever the caller passes via ``prenight_visits``.  schedview
deliberately provides no helper for this step yet — that functionality may
eventually live in ``rubin_sim.sim_archive``.  The caller (e.g. the
``schedview_reports_toc`` Times Square notebook) is responsible for selecting
and reading the appropriate simulation for the night.  The procedure, using
``rubin_sim.sim_archive``:

.. code-block:: python

    from rubin_sim.sim_archive.prenightindex import (
        get_prenight_index, select_latest_prenight_sim)
    from rubin_sim.sim_archive import vseqarchive
    from schedview.collect.visits import NIGHT_STACKERS
    from schedview import DayObs

    day_obs = DayObs.from_date("today")
    # lsstcam is mounted on simonyi; latiss on auxtel.
    sims = get_prenight_index(day_obs.date, telescope="simonyi")
    sim = select_latest_prenight_sim(sims)  # dict or None
    if sim is not None:
        prenight_visits = vseqarchive.get_visits(
            sim["visitseq_url"],
            query=f"floor(observationStartMJD-0.5)=={day_obs.mjd}",
            stackers=NIGHT_STACKERS,
        )

The returned visits carry ``t_eff`` and ``visitExposureTime`` columns and are
passed to ``make_report_rss_feed`` unmodified.
``schedview.collect.multisim.read_multiple_prenights`` is a working example of
this same ``get_prenight_index`` → ``vseqarchive.get_visits`` sequence.


**Basic RSS generation (no visits):**

>>> import datetime
>>> import xml.etree.ElementTree as ET
>>> import pandas as pd
>>> from schedview.reports import make_report_rss_feed

>>> reports = pd.DataFrame([
...     {"night": datetime.date.today(), "dayobs": "20250620",
...      "report": "nightsum", "instrument": "lsstcam",
...      "url": "http://example.com/ns",
...      "link": '<a href="#">nightsum</a>',
...      "report_time": "2025-06-20T12:00:00+00:00", "fname": "ns.html"},
... ]).set_index(["instrument", "dayobs"]).sort_values("night", ascending=False)
>>> tree = make_report_rss_feed(reports, fname=None, max_days=99999)
>>> isinstance(tree, ET.ElementTree)
True
>>> root = tree.getroot()
>>> root.tag
'rss'
>>> root.attrib["version"]
'2.0'

**Title parameter controls channel title:**

>>> tree = make_report_rss_feed(
...     reports, fname=None, max_days=99999, title="My Custom Title"
... )
>>> tree.getroot().find("channel/title").text
'My Custom Title'

**Description parameter controls channel description:**

>>> tree = make_report_rss_feed(
...     reports, fname=None, max_days=99999,
...     description="Custom description"
... )
>>> tree.getroot().find("channel/description").text
'Custom description'

**Prenight visits populate the prenight item description:** the simulation
visits use ``t_eff`` and ``visitExposureTime`` and are passed unmodified.

>>> import numpy as np
>>> prenight_reports = pd.DataFrame([
...     {"night": datetime.date.today(), "dayobs": "20250620",
...      "report": "prenight", "instrument": "lsstcam",
...      "url": "http://example.com/pn",
...      "link": '<a href="#">prenight</a>',
...      "report_time": "2025-06-20T12:00:00+00:00", "fname": "pn.html"},
... ]).set_index(["instrument", "dayobs"]).sort_values("night", ascending=False)
>>> rng = np.random.default_rng(0)
>>> n = 20
>>> prenight_visits = pd.DataFrame({
...     "dayObs": np.full(n, 20250620),
...     "observationId": np.arange(n),
...     "seeingFwhmGeom": rng.uniform(0.6, 1.8, size=n),
...     "t_eff": rng.uniform(20.0, 40.0, size=n),
...     "visitExposureTime": rng.uniform(25.0, 35.0, size=n),
...     "band": rng.choice(list("ugrizy"), size=n),
...     "science_program": rng.choice(["BLOCK-365", "ENG-001"], size=n),
...     "target_name": rng.choice(["COSMOS", "XMM-LSS", ""], size=n),
... })
>>> tree = make_report_rss_feed(
...     prenight_reports, fname=None, max_days=99999,
...     prenight_visits=prenight_visits,
... )
>>> desc = tree.getroot().find("channel/item/description").text
>>> "Total visits:" in desc
True


Display Formatting
------------------

The link table applies several formatting rules to ensure clean
presentation:

1. **Float rounding**: All columns in ``FLOAT_SUMMARY_COLUMNS`` are
   rounded to 2 decimal places before rendering.

2. **Object dtype conversion**: Summary columns are cast to ``object``
   dtype before calling ``fillna("")``.  This ensures uniform behavior
   across nullable integer (``Int64``) and floating-point columns that
   would otherwise reject string fill values.

3. **NaN/None suppression**: ``fillna("")`` replaces all missing values
   with empty strings so that the rendered HTML table shows blank cells
   rather than "NaN" or "None".


Changes from ``main``
---------------------

1. **New parameter on ``make_report_link_table``**: ``visits`` (optional).
2. **New parameters on ``make_report_rss_feed``**: ``visits``, ``title``,
   ``description``, ``prenight_visits``.
3. **New private helper** ``_format_summary_desc`` in ``schedview.reports``,
   shared by the nightsum and prenight description branches.
4. **Prenight descriptions**: lsstcam ``prenight`` items get a formatted
   summary from ``prenight_visits`` (a prenight simulation), or a blank
   description when no simulation visits match the night.
5. **Removed** ``"preprogress"`` from the default ``report_columns`` tuple
   in ``make_report_link_table``.
6. **New constants**: ``RSS_DESC_FORMAT``, ``INT_SUMMARY_COLUMNS``,
   ``FLOAT_SUMMARY_COLUMNS``, ``SUMMARY_COLUMNS``.
7. **New imports**: ``numpy``, ``rubin_scheduler.site_models.Almanac``,
   ``schedview.compute.smallsum.compute_tinysum``.
8. **RSS item titles** changed from ``"{report} report for ..."`` to
   ``"{report} for ..."``.
9. **Variable naming** in ``make_report_rss_feed`` changed to avoid
   shadowing the ``title`` parameter (``title`` → ``channel_title_elem``,
   etc.).


Dependencies
------------

- ``pandas``
- ``numpy``
- ``rubin_scheduler.site_models.Almanac`` (for night-hours computation
  inside ``compute_tinysum``)
- ``schedview.compute.smallsum.compute_tinysum`` (the per-night summary
  engine)


Test Coverage
-------------

Tests are in ``tests/test_reports.py``.

``test_make_report_link_table_with_visits``
    Constructs a synthetic visits DataFrame matching the test fixture's
    dayObs values, passes it to ``make_report_link_table``, and verifies:

    - The returned HTML is parseable as XML (well-formed table).
    - The ``"Total"`` and ``"science"`` column headers appear in the output.

``test_make_report_rss_feed_uses_title_parameter``
    Passes a custom ``title`` string and verifies the ``<channel><title>``
    element contains exactly that text.

``test_make_report_rss_feed_prenight_description``
    Passes a synthetic ``prenight_visits`` DataFrame (using the simulator
    ``t_eff``/``visitExposureTime`` columns) whose dayObs match the report
    fixtures, and verifies the ``lsstcam`` ``prenight`` item descriptions carry
    a populated ``Total visits: N (...)`` summary with a band breakdown.

``test_make_report_rss_feed_prenight_blank_when_no_visits``
    Passes ``prenight_visits`` whose dayObs match no report night, and verifies
    every ``prenight`` item description is empty (no fallback text).

Pre-existing tests (``test_find_reports``, ``test_make_report_link_table``,
``test_make_report_rss_feed``) continue to pass and verify backward
compatibility when ``visits`` is not supplied.
