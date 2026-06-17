# Design: Add Caching to `schedview.collect.visits`

## Goal

Add a local file cache layer to `schedview.collect.visits.read_visits` (and `read_ddf_visits`) so that expensive consdb queries can be avoided on repeated calls for the same data. The cache is optional and fully backward-compatible: when no cache directory is specified, the functions behave exactly as they do today.

## Source Context

- **Reference notebook:** `notebooks/smallsum.ipynb` — contains the prototype `cached_read_visits` function that this design formalizes.
- **Target module:** `schedview/collect/visits.py` — contains the existing `read_visits` and `read_ddf_visits` functions.
- **Compatibility note:** The final implementation must be backward compatible with the existing `schedview.collect.visits` API, but need not exactly replicate the notebook's implementation. The notebook is a prototype; this design is the authoritative specification.

## Overview

The notebook's `cached_read_visits` function:
1. Constructs a cache file path based on instrument and whether it's DDF.
2. Checks whether the cache file is "fresh enough" (modified after yesterday's sunrise and before today's sunset).
3. If fresh, reads from the cache; otherwise queries the real source, then writes the result back to the cache.
4. Filters the returned DataFrame down to visits on or before the requested `day_obs`.

The design below incorporates that logic into the existing module in a clean, testable, backward-compatible way.

---

## Detailed Design

### 1. Module-level configuration variables

Add module-level variables that control caching behavior:

```python
VISITS_CACHE_DIR: str | Path | None = None
VISITS_CACHE_FORMAT: str = "parquet"  # "parquet" or "hdf5"
```

When `VISITS_CACHE_DIR` is `None`, caching is disabled by default (preserving backward compatibility). Users or deployment configurations can set these once at startup:

```python
import schedview.collect.visits
schedview.collect.visits.VISITS_CACHE_DIR = "/path/to/cache"
schedview.collect.visits.VISITS_CACHE_FORMAT = "parquet"  # or "hdf5"
```

`VISITS_CACHE_FORMAT` controls the serialization format for cache files. Supported values are:
- `"parquet"` — Apache Parquet format via `pd.read_parquet`/`pd.to_parquet`. Default. Faster, smaller files, no `pytables` dependency required.
- `"hdf5"` — HDF5 format via `pd.read_hdf`/`pd.to_hdf` with key `"visits"`. Consistent with existing caching elsewhere in schedview (e.g., rewards caching). Requires `pytables`.

### 2. New parameter on `read_visits` (and propagated through `read_ddf_visits`)

Add an optional `cache_dir` parameter that defaults to the module-level variable:

```python
def read_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    stackers: list[...] = ...,
    num_nights: int = 1,
    cache_dir: str | Path | None = VISITS_CACHE_DIR,   # <-- NEW
    **kwargs,
) -> pd.DataFrame:
```

Because `VISITS_CACHE_DIR` is `None` by default, callers who never set it get identical behavior to today. Callers who set the module-level variable get caching everywhere automatically, and can still override per-call with an explicit `cache_dir=` argument.

**Implementation note:** To pick up runtime changes to `VISITS_CACHE_DIR`, use a sentinel default rather than binding at function-definition time:

```python
_USE_MODULE_DEFAULT = object()

def read_visits(..., cache_dir=_USE_MODULE_DEFAULT, ...):
    if cache_dir is _USE_MODULE_DEFAULT:
        cache_dir = VISITS_CACHE_DIR
    ...
```

### 3. New private helper: `_resolve_cache_path`

```python
def _resolve_cache_path(
    cache_dir: Path,
    visit_source: str,
    ddf: bool = False,
) -> Path | None:
```

**Purpose:** Determine the cache file path for a given source/mode, or return `None` if caching is not applicable (e.g. the source is an opsim file, not a consdb instrument).

**Logic:**
- Only cache when `visit_source` is a known consdb instrument (i.e., `visit_source in KNOWN_INSTRUMENTS`). The known instruments are imported from `rubin_scheduler.utils.consdb.KNOWN_INSTRUMENTS` and currently include `"lsstcam"` and `"latiss"`. Opsim/baseline/file sources are already local and fast; caching them would be confusing.
- File naming depends on `VISITS_CACHE_FORMAT`:
  - If `"parquet"`: `visits_{visit_source}.parquet` or `visits_{visit_source}_ddf.parquet`
  - If `"hdf5"`: `visits_{visit_source}.h5` or `visits_{visit_source}_ddf.h5`
- Returns `cache_dir / <filename>`.

**Notebook reference:** The notebook checks `visit_origin in ("lsstcam", "latiss")` — this design generalizes that by using `KNOWN_INSTRUMENTS` which is already imported in the module.

### 4. New private helper: `_is_cache_fresh`

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

### 5. New private helper: `_read_cache` and `_write_cache`

```python
def _read_cache(cache_path: Path) -> pd.DataFrame:
    """Read a visits DataFrame from the cache file.

    Dispatches based on file extension (.parquet or .h5).
    """
    if cache_path.suffix == ".parquet":
        return pd.read_parquet(cache_path)
    else:
        return pd.read_hdf(str(cache_path), key="visits")


def _write_cache(visits: pd.DataFrame, cache_path: Path) -> None:
    """Write a visits DataFrame to the cache file.

    Dispatches based on file extension (.parquet or .h5).
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.suffix == ".parquet":
        visits.to_parquet(cache_path, compression="zstd")
    else:
        visits.to_hdf(str(cache_path), key="visits")
```

**Format dispatch:** `_read_cache` and `_write_cache` dispatch on the file extension of `cache_path` (which is set by `_resolve_cache_path` based on `VISITS_CACHE_FORMAT`). This means the format decision is made in one place (`_resolve_cache_path`) and the read/write helpers are format-agnostic beyond checking the extension.

**Format notes:**
- **Parquet** — requires `pyarrow` (already a transitive dependency via pandas in most environments). Produces smaller files, faster reads, and does not require `pytables`. Uses Zstd compression for an excellent balance of compression ratio and speed. Handles most pandas column types well, but note that columns with mixed types or complex Python objects may need care.
- **HDF5** — requires `pytables` (already available in the schedview environment). Consistent with existing caching elsewhere in schedview (e.g., rewards caching). More tolerant of exotic column dtypes.

**Migration/coexistence:** If a user changes `VISITS_CACHE_FORMAT` after a cache was already written, the old cache file (with the previous extension) will simply not be found by `_resolve_cache_path` (since the filename extension will differ). The next call will be a cache miss, re-query, and write a new file in the new format. The old file is left in place (not automatically deleted). This is safe and simple.

### 6. Modified `read_visits` logic

The body of `read_visits` changes to:

```
1. If cache_dir is not None:
   a. cache_path = _resolve_cache_path(cache_dir, visit_source, ddf=False)
   b. If cache_path is not None and _is_cache_fresh(cache_path):
      - visits = _read_cache(cache_path)
      - Filter to visits with dayObs <= requested day_obs
      - Return visits

2. (Existing logic) Query consdb or read from opsim as before.

3. If cache_dir is not None and cache_path is not None:
   - _write_cache(visits, cache_path)

4. Return visits
```

Note: Step 1b includes a filtering step so that the cache (which stores *all* visits up to the last completed night) can serve requests for any day_obs up to that point without re-querying. This requires that `dayObs` is a column in the cached DataFrame. The existing consdb path (via `DayObsStacker`) and opsim path (via `DayObsStacker` in `NIGHT_STACKERS`) both provide this column when the standard stackers are used.

**Important:** The filtering in step 1b requires a `dayObs` column. If this column is not present in the cached data (because non-standard stackers were used), skip the filtering and return the full cached DataFrame. This avoids breaking callers who use custom stacker lists.

**Cache population strategy (from notebook):** When populating the cache on a miss, the query should fetch *all* visits up to today (using `num_nights=365*20` or an equivalently large window and `day_obs=DayObs.from_date('today')`), not just the visits for the originally-requested `day_obs`/`num_nights` range. This ensures the cache is comprehensive and can serve future requests for any historical day_obs without re-querying. The `day_obs` and `num_nights` parameters from the original call are only used for the final filtering step, not for the cache-populating query.

**Filtering detail:** The notebook filters using `all_visits.loc[all_visits.dayObs <= day_obs.yyyymmdd, :]`, where `dayObs` is an integer column in `YYYYMMDD` format (produced by `maf.stackers.DayObsStacker()`). The `day_obs` comparison value should be converted via `DayObs.from_date(day_obs).yyyymmdd` (an integer). Additionally, when `num_nights > 1`, the filter should also enforce a lower bound: `dayObs > (requested_day_obs - num_nights)` to match the semantics of the non-cached path.

### 7. Modified `read_ddf_visits` logic

`read_ddf_visits` already delegates to `read_visits`. It simply needs to:
- Accept `cache_dir` and pass it through to `read_visits`.
- Use a distinct cache file name. This is handled by adding a `_ddf` parameter or by constructing the cache path before calling `read_visits`.

**Approach:** Add a private `_cache_suffix` parameter to `read_visits` (defaulting to `""`) that `read_ddf_visits` sets to `"_ddf"`. This avoids duplicating caching logic. Alternatively, `read_ddf_visits` can manage its own cache path and pass `cache_dir=None` to `read_visits` (managing caching entirely at the `read_ddf_visits` level).

**Chosen approach:** `read_ddf_visits` manages its own caching independently. It will:
1. Check for a fresh DDF cache file (named with `_ddf` suffix).
2. If fresh, read from cache.
3. Otherwise, call `read_visits(..., cache_dir=None)` to get fresh data (no double-caching), then do its DDF field filtering, then write its own cache.

This keeps the two caching paths independent and avoids confusion.

**Notebook reference:** The notebook's `cached_read_visits` function uses the `ddf` boolean parameter to switch between calling `schedview.collect.visits.read_ddf_visits` (with `DDF_STACKERS + [maf.stackers.DayObsStacker()]`) and `schedview.collect.visits.read_visits` (with `NIGHT_STACKERS`). In this design, both `read_visits` and `read_ddf_visits` handle their own caching, so callers do not need a separate `cached_read_visits` wrapper.

**DDF stacker note:** The notebook adds `maf.stackers.DayObsStacker()` to `DDF_STACKERS` when populating the DDF cache. The current `DDF_STACKERS` list does not include `DayObsStacker`. For the cache filtering (by `dayObs` column) to work in `read_ddf_visits`, `DayObsStacker` must be included in the stackers used for the cache-populating query. The implementation should ensure this stacker is added when building the cache, even if the caller did not include it. Alternatively, `DDF_STACKERS` could be updated to include `DayObsStacker()` at the module level (this would be a minor behavior change but harmless since the stacker only adds a column).

### 8. Logging

Add `logging.getLogger(__name__)` at the top of the module. Log at `debug` level:
- "Reading visits from cache: {cache_path}"
- "Cache miss or stale, querying source: {visit_source}"
- "Writing visits cache: {cache_path}"

---

## Backward Compatibility

- `VISITS_CACHE_DIR` is `None` by default, so `cache_dir` defaults to `None` → no caching → identical to current behavior.
- No new required dependencies. Parquet support via `pyarrow` is already a transitive dependency; HDF5 support via `pytables` is already used elsewhere in schedview.
- The function signatures only gain an optional keyword argument.
- The `__init__.py` exports do not change (though `VISITS_CACHE_DIR` may optionally be added to `__all__` for discoverability).

## File Changes Summary

| File | Change |
|------|--------|
| `schedview/collect/visits.py` | Add `VISITS_CACHE_DIR` and `VISITS_CACHE_FORMAT` module-level variables; add `cache_dir` param to `read_visits` and `read_ddf_visits`; add `_resolve_cache_path`, `_is_cache_fresh`, `_read_cache`, `_write_cache` helpers; add sentinel-based default resolution; add caching logic; add logger. |

No changes needed to `__init__.py`, `consdb.py`, `opsim.py`, or any other module.

## Testing Notes

- Unit tests for `_is_cache_fresh` can mock file mtime and `DayObs.from_date`.
- Unit tests for `_resolve_cache_path` verify path construction and `None` return for non-instrument sources.
- Integration tests for `read_visits` with `cache_dir` can use a temp directory and a simulated opsim source (since opsim sources won't actually cache, test the "cache not applicable" path), or mock `read_consdb` to verify the cache-hit path.
- Test that calling `read_visits` twice with the same `cache_dir` produces the same result, and the second call reads from the file (mock `read_consdb` to verify it's not called twice).

## Existing Module Structure Reference

The current `schedview/collect/visits.py` module has these key elements that the implementation must integrate with:

```python
# Imports already present:
from rubin_scheduler.utils.consdb import KNOWN_INSTRUMENTS  # used to detect consdb instruments
from schedview import DayObs  # day_obs handling

# Module constants already present:
NIGHT_STACKERS = [...]   # includes DayObsStacker
DDF_STACKERS = [...]     # does NOT include DayObsStacker (see DDF stacker note above)

# New module constants to add:
VISITS_CACHE_DIR: str | Path | None = None
VISITS_CACHE_FORMAT: str = "parquet"  # "parquet" or "hdf5"

# read_visits signature:
def read_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    stackers: list[...] = [maf.stackers.ObservationStartTimestampStacker()],
    num_nights: int = 1,
    **kwargs,
) -> pd.DataFrame:

# read_ddf_visits signature:
def read_ddf_visits(*args, **kwargs) -> pd.DataFrame:
    # Sets default stackers to DDF_STACKERS if not provided
    # Calls read_visits(*args, **kwargs) internally
    # Filters results to DDF fields using target_name/scheduler_note columns
```

## Development Environment

- Virtual environment: `/home/neilsen/devel/schedview/.venv`
- Package manager: `uv`
- The `pytables` dependency (for HDF5 I/O via `pd.read_hdf`/`pd.to_hdf`) is already available in the environment.
- The `pyarrow` dependency (for Parquet I/O via `pd.read_parquet`/`pd.to_parquet`) is already available in the environment.
