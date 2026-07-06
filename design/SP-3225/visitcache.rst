============================================================
Design: Caching for ``schedview.collect.visits``
============================================================

Goal
----

Add a local file cache layer for expensive consdb queries so they can be
avoided on repeated calls for the same data.  The cache is implemented as a
standalone ``cached_read_visits`` function that wraps
``read_visits``/``read_ddf_visits``.

Source Context
--------------

- **Reference notebook:** ``notebooks/smallsum.ipynb`` — contains the
  prototype ``cached_read_visits`` function that this design formalizes.
- **Target module:** ``schedview/collect/visits.py`` — contains the existing
  ``read_visits`` and ``read_ddf_visits`` functions, plus the new
  ``cached_read_visits`` and ``_is_cache_fresh`` helpers.

Architecture
------------

The caching layer consists of one public function and one private helper:

``cached_read_visits(day_obs, visit_source, cache_dir, stackers, ddf)``
    The public entry point.  On a **cache hit** (the cache file exists, is
    fresh, and was built with the same set of stackers), it reads from the
    local HDF5 file.  On a **cache miss**, it queries the real source via
    ``read_visits`` / ``read_ddf_visits``, writes the result to the cache,
    and returns the filtered data.

``_is_cache_fresh(cache_path)``
    Determines whether a cache file is "fresh enough" to use based on its
    modification time relative to yesterday's sunrise and today's sunset.

The flow for a single call:

1. **Validate** ``visit_source`` — only consdb instruments are supported.
2. **Resolve** default stackers based on the ``ddf`` flag.
3. **Construct** the cache file path from ``cache_dir``, ``visit_source``,
   and the ``ddf`` flag.
4. **Check freshness** via ``_is_cache_fresh``.
5. If fresh, **verify stacker match** by comparing stored class names to the
   requested set.
6. On a miss, **query** the source for all available history, then **write**
   the HDF5 cache with both ``"visits"`` and ``"stackers"`` keys.
7. **Filter** the result to visits on or before the requested ``day_obs``.

The sections below describe each component in detail, with embedded doctests
that verify the implementation follows the design.


Module Location
---------------

::

    schedview/collect/visits.py

Exported from ``schedview.collect`` via ``__init__.py``:

.. code-block:: python

    from .visits import NIGHT_STACKERS, cached_read_visits, read_visits


Public Function: ``cached_read_visits``
---------------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def cached_read_visits(
        day_obs: str | int | DayObs,
        visit_source: str,
        cache_dir: str | Path,
        stackers: list | None = None,
        ddf: bool = False,
    ) -> pd.DataFrame:

Parameters
~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Parameter
     - Type
     - Description
   * - ``day_obs``
     - ``str | int | DayObs``
     - The night of observing.  Visits up to and including this night are
       returned.
   * - ``visit_source``
     - ``str``
     - A consdb instrument name (e.g. ``"lsstcam"``, ``"latiss"``).  Only
       sources in ``KNOWN_INSTRUMENTS`` are supported; raises ``ValueError``
       otherwise.
   * - ``cache_dir``
     - ``str | Path``
     - Directory where cache files are stored.  Created automatically if it
       does not exist.
   * - ``stackers``
     - ``list | None``
     - Stacker instances to apply.  If ``None``, defaults to
       ``NIGHT_STACKERS`` (when ``ddf=False``) or
       ``DDF_STACKERS + [maf.stackers.DayObsStacker()]`` (when ``ddf=True``).
   * - ``ddf``
     - ``bool``
     - If ``True``, use ``read_ddf_visits`` instead of ``read_visits`` and
       use DDF-appropriate stackers.

Returns
~~~~~~~

A ``pd.DataFrame`` of visits for nights up to and including ``day_obs``.

Raises
~~~~~~

``ValueError``
    If ``visit_source`` is not a known consdb instrument.


Input validation
~~~~~~~~~~~~~~~~

Only consdb instrument names are accepted.  Other source types (opsim
files, ``"baseline"``) raise ``ValueError``:

>>> import warnings
>>> warnings.filterwarnings("ignore")
>>> from schedview.collect.visits import cached_read_visits

>>> try:
...     cached_read_visits(20260614, "baseline", cache_dir="/tmp/cache")
... except ValueError as e:
...     "only supports consdb instruments" in str(e)
True

>>> try:
...     cached_read_visits(20260614, "/path/to/sim.db", cache_dir="/tmp/c")
... except ValueError as e:
...     "only supports consdb instruments" in str(e)
True


Cache File Format
-----------------

The cache file is an **HDF5** file (``.h5`` extension) with two keys:

- ``"visits"`` — the full visits ``DataFrame`` (all nights up to the query
  date).
- ``"stackers"`` — a single-column ``DataFrame`` (column ``"class_name"``)
  recording the fully-qualified class name of each stacker used to produce
  the cached data.  Used to detect stale caches caused by a change in the
  requested stacker set.

File Naming
~~~~~~~~~~~

- Non-DDF: ``visits_{visit_source}.h5`` (e.g. ``visits_lsstcam.h5``)
- DDF: ``visits_{visit_source}_ddf.h5`` (e.g. ``visits_lsstcam_ddf.h5``)

The DDF suffix ensures that DDF and non-DDF caches coexist without
collision:

>>> import tempfile
>>> from pathlib import Path
>>> from unittest.mock import MagicMock, patch
>>> import pandas as pd
>>> from schedview.collect.visits import cached_read_visits

>>> fake_visits = pd.DataFrame({
...     "dayObs": [20260610, 20260611, 20260612],
...     "observationId": range(3),
... })
>>> def _day_obs_mock(yyyymmdd):
...     m = MagicMock()
...     m.yyyymmdd = yyyymmdd
...     return m

Non-DDF creates ``visits_lsstcam.h5``:

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, ddf=False
...         )
...     (Path(tmpdir) / "visits_lsstcam.h5").exists()
True

DDF creates ``visits_lsstcam_ddf.h5``:

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_ddf_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, ddf=True
...         )
...     (Path(tmpdir) / "visits_lsstcam_ddf.h5").exists()
True

HDF5 Structure
~~~~~~~~~~~~~~

On a cache miss, both the ``"visits"`` and ``"stackers"`` keys are written.
The ``"stackers"`` key stores a DataFrame with one row per stacker class:

>>> from rubin_sim import maf
>>> stackers = [maf.stackers.DayObsStacker()]
>>> def _class_names(stackers):
...     return {type(s).__module__ + "." + type(s).__qualname__
...             for s in stackers}

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers
...         )
...     cache_path = Path(tmpdir) / "visits_lsstcam.h5"
...     stored_visits = pd.read_hdf(str(cache_path), key="visits")
...     stored_stackers = pd.read_hdf(str(cache_path), key="stackers")
...     len(stored_visits)
...     "class_name" in stored_stackers.columns
...     set(stored_stackers["class_name"]) == _class_names(stackers)
3
True
True


Private Helper: ``_is_cache_fresh``
-----------------------------------

Signature
~~~~~~~~~

.. code-block:: python

    def _is_cache_fresh(cache_path: Path) -> bool

Purpose
~~~~~~~

Determine whether a cache file is "fresh enough" to use.

Logic
~~~~~

- If the file does not exist, return ``False``.
- Get the file's modification time as an ``astropy.time.Time``.
- Compute boundaries:

  - ``yesterday = DayObs.from_date("yesterday")``
  - ``today = DayObs.from_date("today")``
  - Lower bound: ``yesterday.sunrise`` (the cache was written after the
    last night ended)
  - Upper bound: ``today.sunset`` (the cache was written before tonight
    starts)

- Return ``True`` if ``lower_bound < cache_mtime < upper_bound``.

Rationale
~~~~~~~~~

The cache represents "all visits through last night."  If it was written
between yesterday's sunrise (after last night ended) and today's sunset
(before tonight starts), it should be complete and not yet stale.

**Missing file returns False:**

>>> from schedview.collect.visits import _is_cache_fresh
>>> _is_cache_fresh(Path("/nonexistent/path/visits_lsstcam.h5"))
False

**Fresh file returns True** (mtime within the freshness window):

>>> from astropy.time import Time
>>> with tempfile.TemporaryDirectory() as tmpdir:
...     cache_path = Path(tmpdir) / "visits_lsstcam.h5"
...     _ = cache_path.write_bytes(b"fake")
...     yesterday_dayobs = MagicMock()
...     yesterday_dayobs.sunrise = Time(
...         "2026-06-16 10:00:00", scale="utc"
...     )
...     today_dayobs = MagicMock()
...     today_dayobs.sunset = Time(
...         "2026-06-18 01:00:00", scale="utc"
...     )
...     mock_stat = MagicMock()
...     mock_stat.st_mtime = Time(
...         "2026-06-17 12:00:00", scale="utc"
...     ).unix
...     with (
...         patch("pathlib.Path.stat", return_value=mock_stat),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda arg: yesterday_dayobs if arg == "yesterday"
...             else today_dayobs
...         )
...         _is_cache_fresh(cache_path)
True

**Stale file returns False** (mtime before the freshness window):

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     cache_path = Path(tmpdir) / "visits_lsstcam.h5"
...     _ = cache_path.write_bytes(b"fake")
...     mock_stat = MagicMock()
...     mock_stat.st_mtime = Time(
...         "2026-06-10 12:00:00", scale="utc"
...     ).unix
...     yesterday_dayobs = MagicMock()
...     yesterday_dayobs.sunrise = Time(
...         "2026-06-16 10:00:00", scale="utc"
...     )
...     today_dayobs = MagicMock()
...     today_dayobs.sunset = Time(
...         "2026-06-18 01:00:00", scale="utc"
...     )
...     with (
...         patch("pathlib.Path.stat", return_value=mock_stat),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda arg: yesterday_dayobs if arg == "yesterday"
...             else today_dayobs
...         )
...         _is_cache_fresh(cache_path)
False


Cache Hit/Miss Logic
--------------------

The cache hit/miss decision follows this sequence:

1. Validate ``visit_source`` is in ``KNOWN_INSTRUMENTS`` (raise
   ``ValueError`` if not).
2. Resolve default stackers based on the ``ddf`` flag.
3. Construct ``cache_path``:
   ``cache_dir / f"visits_{visit_source}{suffix}.h5"``
   where ``suffix = "_ddf"`` if ``ddf`` else ``""``.
4. Compute ``requested_class_names`` = set of fully-qualified class names
   from stackers.
5. If ``_is_cache_fresh(cache_path)``:

   a. Try to read the ``"stackers"`` key from the HDF5 file.
   b. If the key is missing, treat as a stale cache → cache miss.
   c. If ``cached_class_names == requested_class_names`` → cache hit:
      read ``"visits"`` key from HDF5.
   d. If class names don't match → cache miss (stacker mismatch).

6. On cache miss:

   a. Query source using ``read_visits`` or ``read_ddf_visits`` with:
      ``day_obs = DayObs.from_date("today")``,
      ``num_nights = 365 * 20`` (fetch all available history),
      ``stackers = resolved stackers``.
   b. Create ``cache_dir`` if it doesn't exist.
   c. Write visits to HDF5 under key ``"visits"`` (``mode="w"``).
   d. Write stacker class names to HDF5 under key ``"stackers"``
      (``mode="a"``).

7. Filter to requested ``day_obs``:

   - If ``"dayObs"`` column exists: return visits where
     ``dayObs <= day_obs_obj.yyyymmdd``.
   - If ``"dayObs"`` column is absent: warn and return unfiltered data.


Cache hit — read_visits is not called
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the cache is fresh and stackers match, the underlying query function
is not invoked:

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     cache_path = Path(tmpdir) / "visits_lsstcam.h5"
...     fake_visits.to_hdf(str(cache_path), key="visits", mode="w")
...     pd.DataFrame(
...         {"class_name": sorted(_class_names(stackers))}
...     ).to_hdf(str(cache_path), key="stackers", mode="a")
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=True),
...         patch("schedview.collect.visits.read_visits") as mock_rv,
...         patch("schedview.collect.visits.DayObs.from_date",
...               return_value=_day_obs_mock(20260612)),
...     ):
...         result = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers
...         )
...     mock_rv.assert_not_called()
...     len(result)
3

Stacker mismatch triggers regeneration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the cache was built with different stackers than those requested, the
cache is regenerated:

>>> stackers_in_cache = [maf.stackers.DayObsStacker()]
>>> stackers_requested = [
...     maf.stackers.DayObsStacker(),
...     maf.stackers.DayObsISOStacker(),
... ]
>>> with tempfile.TemporaryDirectory() as tmpdir:
...     cache_path = Path(tmpdir) / "visits_lsstcam.h5"
...     fake_visits.to_hdf(str(cache_path), key="visits", mode="w")
...     pd.DataFrame(
...         {"class_name": sorted(_class_names(stackers_in_cache))}
...     ).to_hdf(str(cache_path), key="stackers", mode="a")
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=True),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits) as mock_rv,
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir,
...             stackers=stackers_requested,
...         )
...     mock_rv.assert_called_once()
...     new_names = set(
...         pd.read_hdf(str(cache_path), key="stackers")["class_name"]
...     )
...     new_names == _class_names(stackers_requested)
True


Filtering and Warnings
-----------------------

dayObs filtering
~~~~~~~~~~~~~~~~

Results are filtered to visits on or before the requested ``day_obs``:

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260611)
...         )
...         result = cached_read_visits(
...             20260611, "lsstcam", cache_dir=tmpdir
...         )
...     list(result["dayObs"])
[20260610, 20260611]

Missing dayObs column
~~~~~~~~~~~~~~~~~~~~~~

If the visits DataFrame lacks a ``"dayObs"`` column (e.g. because
``DayObsStacker`` was not in the stacker list), a warning is issued and
unfiltered data is returned:

>>> fake_visits_no_dayobs = pd.DataFrame({"observationId": [1, 2, 3]})
>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits_no_dayobs),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260614)
...         )
...         with warnings.catch_warnings(record=True) as w:
...             warnings.simplefilter("always")
...             result = cached_read_visits(
...                 20260614, "lsstcam", cache_dir=tmpdir
...             )
...     len(result)
...     any("dayObs" in str(warning.message) for warning in w)
3
True


Default Stackers
-----------------

When ``stackers=None``, the function selects appropriate defaults:

- **Non-DDF**: ``NIGHT_STACKERS``
- **DDF**: ``DDF_STACKERS + [maf.stackers.DayObsStacker()]``

Non-DDF defaults
~~~~~~~~~~~~~~~~~

>>> from schedview.collect.visits import NIGHT_STACKERS, DDF_STACKERS
>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits) as mock_rv,
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, stackers=None
...         )
...     _, call_kwargs = mock_rv.call_args
...     _class_names(call_kwargs["stackers"]) == _class_names(NIGHT_STACKERS)
True

DDF defaults
~~~~~~~~~~~~~

>>> ddf_default_stackers = DDF_STACKERS + [maf.stackers.DayObsStacker()]
>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_ddf_visits",
...               return_value=fake_visits) as mock_rdv,
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir,
...             stackers=None, ddf=True,
...         )
...     _, call_kwargs = mock_rdv.call_args
...     _class_names(call_kwargs["stackers"]) == _class_names(ddf_default_stackers)
True


Automatic Directory Creation
------------------------------

If ``cache_dir`` does not exist, it is created automatically (including
intermediate directories):

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     new_cache_dir = Path(tmpdir) / "new" / "subdir"
...     new_cache_dir.exists()
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         _ = cached_read_visits(
...             20260612, "lsstcam", cache_dir=new_cache_dir
...         )
...     new_cache_dir.exists()
False
True


Idempotence
-----------

Two consecutive calls with the same parameters return equivalent results —
the first call populates the cache, the second reads from it:

>>> with tempfile.TemporaryDirectory() as tmpdir:
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=False),
...         patch("schedview.collect.visits.read_visits",
...               return_value=fake_visits),
...         patch("schedview.collect.visits.DayObs.from_date") as mock_fd,
...     ):
...         mock_fd.side_effect = (
...             lambda a: MagicMock() if a == "today"
...             else _day_obs_mock(20260612)
...         )
...         result1 = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers
...         )
...     with (
...         patch("schedview.collect.visits._is_cache_fresh",
...               return_value=True),
...         patch("schedview.collect.visits.DayObs.from_date",
...               return_value=_day_obs_mock(20260612)),
...     ):
...         result2 = cached_read_visits(
...             20260612, "lsstcam", cache_dir=tmpdir, stackers=stackers
...         )
...     result1.equals(result2)
True


Logging
-------

Uses ``logging.getLogger(__name__)`` at the module level.  Logs at ``debug``
level:

- ``"Reading visits from cache: {cache_path}"``
- ``"Cache miss or stale, querying source: {visit_source}"``
- ``"Cache missing 'stackers' key, treating as stale: {cache_path}"``
- ``"Cache stacker mismatch, regenerating: {cache_path}"``
- ``"Writing visits cache: {cache_path}"``


Backward Compatibility
-----------------------

- ``read_visits`` and ``read_ddf_visits`` signatures are **unchanged**.
  Caching is provided only through the new ``cached_read_visits`` function.
- ``cached_read_visits`` is exported from ``schedview.collect`` via
  ``__init__.py``.
- No new required dependencies.  HDF5 support via ``pytables`` is already
  used elsewhere in schedview.


Dependencies
------------

- ``pandas`` (``pd.read_hdf``, ``pd.DataFrame.to_hdf``)
- ``astropy.time.Time`` (for cache freshness comparison)
- ``schedview.DayObs`` (for date/time boundaries)
- ``rubin_sim.maf`` (for stacker instances and class name introspection)
- ``rubin_scheduler.utils.consdb.KNOWN_INSTRUMENTS`` (for input validation)
