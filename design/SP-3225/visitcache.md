# Design: Add Caching to `schedview.collect.visits`

## Goal

Add a local file cache layer for expensive consdb queries so they can be avoided on repeated calls for the same data. The cache is implemented as a standalone `cached_read_visits` function that wraps `read_visits`/`read_ddf_visits`.

## Source Context

- **Reference notebook:** `notebooks/smallsum.ipynb` — contains the prototype `cached_read_visits` function that this design formalizes.
- **Target module:** `schedview/collect/visits.py` — contains the existing `read_visits` and `read_ddf_visits` functions, plus the new `cached_read_visits` and `_is_cache_fresh` helpers.

## Overview

The `cached_read_visits` function:
1. Validates the source is a known consdb instrument (raises `ValueError` otherwise).
2. Constructs a cache file path based on instrument and whether it's DDF.
3. Checks whether the cache file is "fresh enough" (modified after yesterday's sunrise and before today's sunset) **and** was built with the same set of stackers.
4. On a cache hit, reads from the HDF5 cache; on a cache miss, queries the real source via `read_visits`/`read_ddf_visits`, writes the result back to the cache.
5. Filters the returned DataFrame down to visits on or before the requested `day_obs`.

---

## Detailed Design

### 1. New public function: `cached_read_visits`

```python
def cached_read_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    cache_dir: str | Path,
    stackers: list | None = None,
    ddf: bool = False,
) -> pd.DataFrame:
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `day_obs` | `str \| int \| DayObs` | The night of observing. Visits up to and including this night are returned. |
| `visit_source` | `str` | A consdb instrument name (e.g. `"lsstcam"`, `"latiss"`). Only sources in `KNOWN_INSTRUMENTS` are supported; raises `ValueError` otherwise. |
| `cache_dir` | `str \| Path` | Directory where cache files are stored. Created automatically if it does not exist. |
| `stackers` | `list \| None` | Stacker instances to apply. If `None`, defaults to `NIGHT_STACKERS` (when `ddf=False`) or `DDF_STACKERS + [maf.stackers.DayObsStacker()]` (when `ddf=True`). |
| `ddf` | `bool` | If `True`, use `read_ddf_visits` instead of `read_visits` and use DDF-appropriate stackers. |

#### Returns

A `pd.DataFrame` of visits for nights up to and including `day_obs`.

#### Raises

- `ValueError` if `visit_source` is not a known consdb instrument.

### 2. Cache File Format

The cache file is an **HDF5** file (`.h5` extension) with two keys:

- `"visits"` — the full visits `DataFrame` (all nights up to the query date).
- `"stackers"` — a single-column `DataFrame` (column `"class_name"`) recording the fully-qualified class name of each stacker used to produce the cached data. Used to detect stale caches caused by a change in the requested stacker set.

**File naming:**
- Non-DDF: `visits_{visit_source}.h5` (e.g. `visits_lsstcam.h5`)
- DDF: `visits_{visit_source}_ddf.h5` (e.g. `visits_lsstcam_ddf.h5`)

### 3. Private helper: `_is_cache_fresh`

```python
def _is_cache_fresh(cache_path: Path) -> bool:
```

**Purpose:** Determine whether a cache file is "fresh enough" to use.

**Logic:**
- If the file does not exist, return `False`.
- Get the file's modification time as an `astropy.time.Time`.
- Compute boundaries:
  - `yesterday = DayObs.from_date("yesterday")`
  - `today = DayObs.from_date("today")`
  - Lower bound: `yesterday.sunrise` (the cache was written after the last night ended)
  - Upper bound: `today.sunset` (the cache was written before tonight starts)
- Return `True` if `lower_bound < cache_mtime < upper_bound`.

**Rationale:** The cache represents "all visits through last night." If it was written between yesterday's sunrise (after last night ended) and today's sunset (before tonight starts), it should be complete and not yet stale.

### 4. Cache hit/miss logic

```
1. Validate visit_source is in KNOWN_INSTRUMENTS (raise ValueError if not).

2. Resolve default stackers based on ddf flag.

3. Construct cache_path:
   - cache_dir / f"visits_{visit_source}{suffix}.h5"
   - where suffix = "_ddf" if ddf else ""

4. Compute requested_class_names = set of fully-qualified class names from stackers.

5. If _is_cache_fresh(cache_path):
   a. Try to read the "stackers" key from the HDF5 file.
   b. If the key is missing, treat as a stale cache → cache miss.
   c. If cached_class_names == requested_class_names → cache hit:
      - Read "visits" key from HDF5.
   d. If class names don't match → cache miss (stacker mismatch).

6. On cache miss:
   a. Query source using read_visits or read_ddf_visits with:
      - day_obs = DayObs.from_date("today")
      - num_nights = 365 * 20  (fetch all available history)
      - stackers = resolved stackers
   b. Create cache_dir if it doesn't exist.
   c. Write visits to HDF5 under key "visits" (mode="w").
   d. Write stacker class names to HDF5 under key "stackers" (mode="a").

7. Filter to requested day_obs:
   - If "dayObs" column exists: return visits where dayObs <= day_obs_obj.yyyymmdd
   - If "dayObs" column is absent: warn and return unfiltered data.
```

### 5. Logging

Uses `logging.getLogger(__name__)` at the module level. Logs at `debug` level:
- `"Reading visits from cache: {cache_path}"`
- `"Cache miss or stale, querying source: {visit_source}"`
- `"Cache missing 'stackers' key, treating as stale: {cache_path}"`
- `"Cache stacker mismatch, regenerating: {cache_path}"`
- `"Writing visits cache: {cache_path}"`

---

## Backward Compatibility

- `read_visits` and `read_ddf_visits` signatures are **unchanged**. Caching is provided only through the new `cached_read_visits` function.
- `cached_read_visits` is exported from `schedview.collect` via `__init__.py`.
- No new required dependencies. HDF5 support via `pytables` is already used elsewhere in schedview.

## File Changes Summary

| File | Change |
|------|--------|
| `schedview/collect/visits.py` | Add `_is_cache_fresh` helper and `cached_read_visits` function; add logger. |
| `schedview/collect/__init__.py` | Add `cached_read_visits` to imports and `__all__`. |

## Testing Notes

- Unit tests for `_is_cache_fresh` mock file mtime and `DayObs.from_date`.
- Tests for `cached_read_visits`:
  - Raises `ValueError` for non-instrument sources.
  - On cache miss: calls `read_visits`, writes HDF5 with both keys.
  - On cache hit: does NOT call `read_visits`; reads from HDF5.
  - Stacker mismatch: regenerates cache.
  - DDF mode: uses `_ddf` suffix in filename, calls `read_ddf_visits`.
  - Default stackers: `NIGHT_STACKERS` for non-DDF, `DDF_STACKERS + [DayObsStacker()]` for DDF.
  - Creates `cache_dir` if absent.
  - Warns when `dayObs` column is missing from data.

## Development Environment

- Virtual environment: `/home/neilsen/devel/schedview/.venv`
- Package manager: `uv`
- The `pytables` dependency (for HDF5 I/O via `pd.read_hdf`/`pd.to_hdf`) is already available in the environment.
