===================================================
Design: ``schedview.compute.smallsum`` Module
===================================================

Overview
--------

This module provides two functions that summarize visits data at the
per-night level:

1. ``compute_tinysum`` – produces a single-row-per-night summary DataFrame
   (the "tiny summary").
2. ``compute_smallsum`` – produces a modest-number-of-rows-per-night summary
   DataFrame (the "small summary"), with rows broken out by subsets (band,
   science/not-science, observation_reason, target name).

Both functions take a visits ``pd.DataFrame`` as their primary input and
return a new summary ``pd.DataFrame``.

Module Location
---------------

::

    schedview/compute/smallsum.py

Registered in ``schedview/compute/__init__.py`` with:

.. code-block:: python

    from .smallsum import compute_tinysum, compute_smallsum


Architecture
------------

The module's two public functions serve different audiences:

- ``compute_tinysum`` produces a **single row per night** suitable for a
  compact dashboard or table-of-contents entry.  It answers the question
  "how did the night go overall?" with counts, efficiency statistics, and
  (optionally) observing-rate metrics.

- ``compute_smallsum`` produces **multiple rows per night**, one for each
  subset category (all visits, each band, science/not-science, each
  observation_reason, each target name).  It answers "how did specific
  categories of observations perform?"

Both functions operate on the same visits ``DataFrame`` produced upstream by
``schedview.collect``, and both are pure computations — no I/O, no side
effects.

Helper functions
~~~~~~~~~~~~~~~~

Three private helpers factor out reusable logic:

``_unique_targets(target_name_series)``
    Aggregates a column of target names into a single deduplicated,
    comma-separated string.  Used by ``compute_tinysum`` to populate the
    ``"science targets"`` column.

``_visits_summary(visits_group)``
    Computes per-group statistics (visit count, time range, effective-time
    quartiles, FWHM, airmass, hour angle).  Used by ``compute_smallsum`` as
    the aggregation function applied to each subset group.

``_build_night_hours(almanac, dayobs_values)``
    Converts an ``Almanac`` instance into a Series mapping each ``dayObs`` to
    its night duration in hours.  Used by ``compute_tinysum`` to derive the
    rate columns (``visits/hour``, ``teff/minute``).

The sections below document each helper's contract and verify it with
embedded doctests, followed by the full specifications of the two public
functions.


Helper: ``_unique_targets``
---------------------------

.. code-block:: python

    def _unique_targets(target_name_series: pd.Series) -> str

Used by ``compute_tinysum`` to aggregate target names per night.

Logic:

- Iterate over each value in the series
- Strip leading ``ddf_`` or ``DDF`` + space prefix (exactly 4 characters)
- Split on ``', '`` to handle multi-target entries
- Collect all non-empty unique targets (preserving first-seen order)
- Return as a comma-separated string

**Prefix stripping**: The ``ddf_`` and ``DDF`` + space prefixes are removed so
that DDF targets are identified by their field name alone:

>>> import numpy as np
>>> import pandas as pd
>>> from schedview.compute.smallsum import _unique_targets
>>> _unique_targets(pd.Series(["ddf_COSMOS", "DDF XMM-LSS"]))
'COSMOS, XMM-LSS'

**Comma splitting**: Multi-target entries (containing ``', '``) are split
into individual targets:

>>> _unique_targets(pd.Series(["ELAIS, XMM-LSS"]))
'ELAIS, XMM-LSS'

**Pass-through**: Plain target names are returned unchanged:

>>> _unique_targets(pd.Series(["COSMOS", "XMM-LSS", "ELAIS"]))
'COSMOS, XMM-LSS, ELAIS'

**Deduplication**: Duplicate targets (including those that become duplicates
after prefix stripping) appear only once:

>>> _unique_targets(pd.Series(["COSMOS", "COSMOS", "ddf_COSMOS"]))
'COSMOS'

**Empty and NaN handling**: Empty strings, ``None``, and ``NaN`` values are
ignored.  If only empty/NaN values are present, the result is an empty
string:

>>> _unique_targets(pd.Series(["", "", "COSMOS"]))
'COSMOS'
>>> _unique_targets(pd.Series([np.nan, None, "COSMOS"]))
'COSMOS'
>>> _unique_targets(pd.Series(["", ""]))
''


Helper: ``_visits_summary``
---------------------------

.. code-block:: python

    def _visits_summary(visits_group: pd.DataFrame) -> pd.Series

Computes summary statistics for a group of visits (one subset of one night).
Returns a ``pd.Series`` with the following keys:

.. list-table::
   :header-rows: 1

   * - Key
     - Computation
   * - ``visits``
     - ``len(visits_group)``
   * - ``first``
     - ``visits_group["start_timestamp"].min()``
   * - ``last``
     - ``visits_group["start_timestamp"].max()``
   * - ``teff_total``
     - ``np.nan_to_num(eff_time_median.to_numpy(), nan=0.0).sum()``
   * - ``teff_q1``
     - ``eff_time_median.quantile(0.25)``
   * - ``teff_median``
     - ``eff_time_median.median()``
   * - ``teff_q3``
     - ``eff_time_median.quantile(0.75)``
   * - ``fwhm_median``
     - ``visits_group["seeingFwhmGeom"].median()``
   * - ``airmass_median``
     - ``visits_group["airmass"].median()``
   * - ``HA_median``
     - ``visits_group["HA"].median()``

Note: ``teff_total`` uses ``np.nan_to_num`` to treat NaN values as 0 before
summing, rather than ``mean * count``, so that nights with partial NaN data
still produce a meaningful total.

**Output keys**: The function returns all expected keys:

>>> from schedview.compute.smallsum import _visits_summary
>>> group = pd.DataFrame({
...     "start_timestamp": [1.0, 2.0, 3.0, 4.0, 5.0],
...     "eff_time_median": [30.0, 25.0, 35.0, 28.0, 32.0],
...     "seeingFwhmGeom": [0.8, 1.0, 0.9, 1.1, 0.7],
...     "airmass": [1.1, 1.2, 1.3, 1.4, 1.5],
...     "HA": [-1.0, -0.5, 0.0, 0.5, 1.0],
... })
>>> result = _visits_summary(group)
>>> sorted(result.index) == sorted([
...     "visits", "first", "last", "teff_total", "teff_q1",
...     "teff_median", "teff_q3", "fwhm_median", "airmass_median",
...     "HA_median",
... ])
True
>>> result["visits"]
np.float64(5.0)
>>> result["first"]
np.float64(1.0)
>>> result["last"]
np.float64(5.0)

**teff_total with NaN**: NaN values in ``eff_time_median`` are treated as 0
when computing the total, so the sum reflects only valid values:

>>> group_with_nan = pd.DataFrame({
...     "start_timestamp": [1.0, 2.0, 3.0],
...     "eff_time_median": [30.0, np.nan, 20.0],
...     "seeingFwhmGeom": [0.8, 1.0, 0.9],
...     "airmass": [1.1, 1.2, 1.3],
...     "HA": [-1.0, 0.0, 1.0],
... })
>>> result = _visits_summary(group_with_nan)
>>> result["teff_total"]
np.float64(50.0)
>>> result["visits"]
np.float64(3.0)

**Single visit**: When only one visit is present, ``first == last``:

>>> single = pd.DataFrame({
...     "start_timestamp": [42.0],
...     "eff_time_median": [30.0],
...     "seeingFwhmGeom": [0.9],
...     "airmass": [1.2],
...     "HA": [0.5],
... })
>>> result = _visits_summary(single)
>>> result["visits"]
np.float64(1.0)
>>> assert result["first"] == result["last"]



Helper: ``_build_night_hours``
------------------------------

.. code-block:: python

    def _build_night_hours(almanac: Almanac, dayobs_values: pd.Index) -> pd.Series

Builds a Series mapping ``dayObs`` (YYYYMMDD int) to night duration in hours,
defined as the time between astronomical twilight boundaries (sun at −12°
setting to sun at −12° rising).

The function uses the Almanac's ``sunsets`` array to look up the
``sun_n12_setting`` and ``sun_n12_rising`` times for each night, computing:

.. code-block:: python

    night_hours = (sun_n12_rising - sun_n12_setting) * 24.0

**Return type and length**: Returns a ``pd.Series`` with the same length as
the input index:

>>> from schedview.compute.smallsum import _build_night_hours
>>> from rubin_scheduler.site_models import Almanac
>>> almanac = Almanac()
>>> index = pd.Index([20250601, 20250602])
>>> result = _build_night_hours(almanac, index)
>>> isinstance(result, pd.Series)
True
>>> len(result) == 2
True

**Positive hours in valid range**: Night durations at Cerro Pachón should
fall between roughly 4 and 12 hours depending on season:

>>> all(4.0 < v < 12.0 for v in result.dropna())
True


Function 1: ``compute_tinysum``
-------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def compute_tinysum(
        visits: pd.DataFrame,
        science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
        almanac: Almanac | None = None,
    ) -> pd.DataFrame:

Parameters
~~~~~~~~~~

``visits`` : ``pd.DataFrame``
    A DataFrame of visits.  Must contain columns: ``dayObs`` (int, YYYYMMDD),
    ``observationId``, ``seeingFwhmGeom``, ``eff_time_median``, ``exp_time``,
    ``band``, ``science_program``, ``target_name``.

``science_programs`` : ``tuple[str, ...]``
    Tuple of ``science_program`` values considered "science".  Defaults to
    ``SCIENCE_PROGRAMS`` from ``rubin_nights.reference_values``.

``almanac`` : ``Almanac`` or ``None``
    A ``rubin_scheduler.site_models.Almanac`` instance.  Pass ``None`` to omit
    the ``night_hours``, ``visits/hour``, and ``teff/minute`` columns.

Returns
~~~~~~~

A ``pd.DataFrame`` indexed by ``dayObs`` (int, YYYYMMDD format), with one row
per night.  Columns:

.. list-table::
   :header-rows: 1

   * - Column
     - Type
     - Description
   * - ``Total``
     - Int64
     - Total number of visits that night (nullable integer)
   * - ``median FWHM``
     - float
     - Median ``seeingFwhmGeom`` across all visits that night
   * - ``total exp_time``
     - float
     - Sum of ``exp_time`` values for the night
   * - ``total eff_time``
     - float
     - Sum of ``eff_time_median`` values for the night
   * - ``mean eff_time``
     - float
     - Mean of ``eff_time_median`` across all visits that night
   * - ``q1 eff_time``
     - float
     - 25th percentile of ``eff_time_median``
   * - ``median eff_time``
     - float
     - 50th percentile of ``eff_time_median``
   * - ``q3 eff_time``
     - float
     - 75th percentile of ``eff_time_median``
   * - ``science``
     - Int64
     - Number of visits with ``science_program`` in ``science_programs``
   * - ``# u`` through ``# y``
     - Int64
     - Number of visits in each band (nullable integer)
   * - ``science targets``
     - str
     - Comma-separated unique target names from science visits
   * - ``total eff_time/exp_time``
     - float
     - ``total eff_time / total exp_time`` (normalized effective time)
   * - ``night_hours``
     - float
     - Duration of night in hours (only if almanac provided)
   * - ``visits/hour``
     - float
     - ``Total / night_hours`` (only if almanac provided)
   * - ``teff/minute``
     - float
     - ``(visits/hour * mean eff_time) / 60`` (only if almanac provided)

Implementation Steps
~~~~~~~~~~~~~~~~~~~~

1. **Basic stats**: Group ``visits`` by ``dayObs``, aggregate:

   - Count of ``observationId`` → ``Total`` (cast to ``Int64``)
   - Median of ``seeingFwhmGeom`` → ``median FWHM``
   - Sum of ``exp_time`` → ``total exp_time``
   - Sum of ``eff_time_median`` → ``total eff_time``

2. **Effective time stats**: Group by ``dayObs``, call ``.describe()`` on
   ``eff_time_median``, extract ``mean``, ``25%``, ``50%``, ``75%`` and rename
   to ``mean eff_time``, ``q1 eff_time``, ``median eff_time``,
   ``q3 eff_time``.

3. **Band counts**: Group by ``['dayObs', 'band']``, count ``observationId``,
   unstack so bands become columns, fill NaN with 0, cast to ``Int64``.
   Rename to ``# u``, ``# g``, etc.

4. **Science counts**: Filter visits where ``science_program`` is in
   ``science_programs``, group by ``dayObs``, count → ``science``.

5. **Science targets**: From science visits, group by ``dayObs``, aggregate
   ``target_name`` using ``_unique_targets``.

6. **Join all** intermediate DataFrames on the ``dayObs`` index.  Fill NaN in
   ``science`` with 0 (cast to ``Int64``) and in ``science targets`` with
   empty string.

7. **Normalized effective time**: Compute
   ``total eff_time/exp_time = total eff_time / total exp_time``.

8. **Night hours** (only if ``almanac`` is not ``None``): Build a mapping from
   ``dayObs`` → night duration via ``_build_night_hours``.

9. **Derived rates** (only if ``almanac`` is not ``None``):

   - ``visits/hour = Total / night_hours``
   - ``teff/minute = visits/hour * mean eff_time / 60``


Function 2: ``compute_smallsum``
--------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def compute_smallsum(
        visits: pd.DataFrame,
        science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
    ) -> pd.DataFrame:

Parameters
~~~~~~~~~~

``visits`` : ``pd.DataFrame``
    A DataFrame of visits.  Must contain columns: ``dayObs``,
    ``observationId``, ``start_timestamp``, ``eff_time_median``,
    ``seeingFwhmGeom``, ``airmass``, ``HA``, ``band``, ``science_program``,
    ``observation_reason``, ``target_name``.

``science_programs`` : ``tuple[str, ...]``
    Tuple of ``science_program`` values considered "science".  Defaults to
    ``SCIENCE_PROGRAMS`` from ``rubin_nights.reference_values``.

Returns
~~~~~~~

A ``pd.DataFrame`` with a two-level index: (``dayObs``, ``subset``).  Each
night has multiple rows, one for each subset category.  The ``subset`` level
contains values like:

- ``"all"`` – aggregate of all visits that night
- Band names (``"u"``, ``"g"``, ``"r"``, ``"i"``, ``"z"``, ``"y"``) – split
  by band
- ``"science"``, ``"not_science"`` – split by whether ``science_program`` is
  in ``science_programs``
- observation_reason values – split by ``observation_reason`` column
- target name values – split by individual target names (with multi-target
  values exploded on ``', '``)

The subset ordering within each night is: ``"all"`` first, then bands, then
science/not_science, then observation_reason, then target names.

Columns of the returned DataFrame:

.. list-table::
   :header-rows: 1

   * - Column
     - Type
     - Description
   * - ``visits``
     - int
     - Number of visits in this subset
   * - ``first``
     - float
     - Earliest ``start_timestamp`` in this subset
   * - ``last``
     - float
     - Latest ``start_timestamp`` in this subset
   * - ``teff_total``
     - float
     - Sum of ``eff_time_median`` with NaN treated as 0
   * - ``teff_q1``
     - float
     - 25th percentile of ``eff_time_median``
   * - ``teff_median``
     - float
     - 50th percentile of ``eff_time_median``
   * - ``teff_q3``
     - float
     - 75th percentile of ``eff_time_median``
   * - ``fwhm_median``
     - float
     - Median ``seeingFwhmGeom``
   * - ``airmass_median``
     - float
     - Median ``airmass``
   * - ``HA_median``
     - float
     - Median hour angle

Implementation Steps
~~~~~~~~~~~~~~~~~~~~

1. **Full night ("all") subset**: Group ``visits`` by ``dayObs``, apply
   ``_visits_summary``.  Add column ``subset = "all"``.  Set index to
   ``(dayObs, subset)``.

2. **By band subset**: Group by ``['dayObs', 'band']``, apply
   ``_visits_summary``.  Rename ``band`` index level to ``subset``.

3. **By science subset**: Add temporary column ``_science`` =
   ``"science"`` or ``"not_science"``.  Group by ``['dayObs', '_science']``,
   apply ``_visits_summary``.  Rename index level to ``subset``.

4. **By observation_reason subset**: Group by
   ``['dayObs', 'observation_reason']``, apply ``_visits_summary``.  Rename
   index level to ``subset``.

5. **By target name subset**: Split ``target_name`` on ``', '`` and explode.
   Replace empty strings with ``"no target name"``.  Group by
   ``['dayObs', '_target_names']``, apply ``_visits_summary``.  Rename index
   level to ``subset``.

6. **Concatenate** in order: all, band, science, observation_reason, target.
   Sort by ``dayObs`` level (preserving order within each night).


Dependencies
------------

- ``pandas``
- ``numpy``
- ``rubin_scheduler.site_models.Almanac`` (for night duration in
  ``compute_tinysum``)
- ``rubin_nights.reference_values.SCIENCE_PROGRAMS`` (default value for
  science program filtering)


Notes
-----

- Both functions are **pure computations**: they take a visits DataFrame and
  return a summary DataFrame.  They do not read data from disk or network.
- The ``visits`` DataFrame is expected to already have the necessary columns
  populated (e.g., via stackers applied during collection).
- The ``dayObs`` column is expected to be an integer in YYYYMMDD format (as
  produced by ``DayObsStacker``).
- The Almanac is only needed by ``compute_tinysum`` for the ``night_hours``
  and rate columns.  If these columns are not needed, the Almanac parameter
  can be set to ``None`` and those columns will be omitted.
- Integer count columns (``Total``, ``science``, band counts) use pandas
  nullable ``Int64`` dtype to avoid float conversion when NaN values are
  present from joins.
- The ``exp_time`` column is required by ``compute_tinysum`` for the
  ``total eff_time/exp_time`` normalized efficiency metric.
