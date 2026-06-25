# Design: `schedview.compute.smallsum` Module

## Overview

This module provides two functions that summarize visits data at the per-night level:

1. **`compute_tinysum`** – produces a single-row-per-night summary DataFrame (the "tiny summary").
2. **`compute_smallsum`** – produces a modest-number-of-rows-per-night summary DataFrame (the "small summary"), with rows broken out by subsets (band, science/not-science, observation_reason, target name).

Both functions take a visits `pd.DataFrame` as their primary input and return a new summary `pd.DataFrame`.

---

## Module Location

```
schedview/compute/smallsum.py
```

It will be registered in `schedview/compute/__init__.py` with:

```python
from .smallsum import compute_tinysum, compute_smallsum
```

---

## Function 1: `compute_tinysum`

### Signature

```python
def compute_tinysum(
    visits: pd.DataFrame,
    science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
    almanac: Almanac | None = None,
) -> pd.DataFrame:
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `visits` | `pd.DataFrame` | A DataFrame of visits. Must contain columns: `dayObs` (int, YYYYMMDD), `observationId`, `seeingFwhmGeom`, `eff_time_median`, `exp_time`, `band`, `science_program`, `target_name`. |
| `science_programs` | `tuple[str, ...]` | Tuple of science_program values considered "science". Defaults to `SCIENCE_PROGRAMS` from `rubin_nights.reference_values`. |
| `almanac` | `Almanac` or `None` | A `rubin_scheduler.site_models.Almanac` instance. Pass `None` to omit the `night_hours`, `visits/hour`, and `teff/minute` columns. |

### Returns

A `pd.DataFrame` indexed by `dayObs` (int, YYYYMMDD format), with one row per night. Columns:

| Column | Type | Description |
|--------|------|-------------|
| `Total` | Int64 | Total number of visits that night (nullable integer) |
| `median FWHM` | float | Median `seeingFwhmGeom` across all visits that night |
| `total exp_time` | float | Sum of `exp_time` values for the night |
| `total eff_time` | float | Sum of `eff_time_median` values for the night |
| `mean eff_time` | float | Mean of `eff_time_median` across all visits that night |
| `q1 eff_time` | float | 25th percentile of `eff_time_median` |
| `median eff_time` | float | 50th percentile of `eff_time_median` |
| `q3 eff_time` | float | 75th percentile of `eff_time_median` |
| `science` | Int64 | Number of visits with `science_program` in `science_programs` (nullable integer) |
| `# u` | Int64 | Number of visits in u band (nullable integer) |
| `# g` | Int64 | Number of visits in g band (nullable integer) |
| `# r` | Int64 | Number of visits in r band (nullable integer) |
| `# i` | Int64 | Number of visits in i band (nullable integer) |
| `# z` | Int64 | Number of visits in z band (nullable integer) |
| `# y` | Int64 | Number of visits in y band (nullable integer) |
| `science targets` | str | Comma-separated unique target names from science visits (with `ddf_`/`DDF ` prefixes stripped; multi-target values split on `, `) |
| `mean eff_time/exp_time` | float | `total eff_time / total exp_time` (normalized effective time) |
| `night_hours` | float | Duration of the night in hours (sun at -12° setting to sun at -12° rising) |
| `visits/hour` | float | `Total / night_hours` |
| `teff/minute` | float | `(visits/hour * mean eff_time) / 60` |

### Implementation Steps

1. **Basic stats**: Group `visits` by `dayObs`, aggregate:
   - Count of `observationId` → `Total` (cast to `Int64`)
   - Median of `seeingFwhmGeom` → `median FWHM`
   - Sum of `exp_time` → `total exp_time`
   - Sum of `eff_time_median` → `total eff_time`

2. **Effective time stats**: Group by `dayObs`, call `.describe()` on `eff_time_median`, extract `mean`, `25%`, `50%`, `75%` and rename to `mean eff_time`, `q1 eff_time`, `median eff_time`, `q3 eff_time`.

3. **Band counts**: Group by `['dayObs', 'band']`, count `observationId`, unstack so bands become columns (`u`, `g`, `r`, `i`, `z`, `y`), fill NaN with 0, cast to `Int64`. Rename to `# u`, `# g`, etc.

4. **Science counts**: Filter visits where `science_program` is in `science_programs`, group by `dayObs`, count → `science`.

5. **Science targets**: From science visits, group by `dayObs`, aggregate `target_name` using a helper function `_unique_targets(values)` that:
   - Strips `ddf_` or `DDF ` prefixes from each value
   - Splits values containing `, ` into sub-targets
   - Returns a comma-separated string of unique targets

6. **Join all** intermediate DataFrames on the `dayObs` index. Fill NaN in `science` with 0 (cast to `Int64`) and in `science targets` with empty string.

7. **Normalized effective time**: Compute `mean eff_time/exp_time` = `total eff_time / total exp_time`.

8. **Night hours** (only if `almanac` is not `None`): Build a mapping from `dayObs` → night duration in hours using the Almanac's `sunsets` array:
   - Convert `night` index to `dayObs` (YYYYMMDD int)
   - Compute `(sun_n12_rising - sun_n12_setting) * 24`

9. **Derived rates** (only if `almanac` is not `None`):
   - `visits/hour` = `Total / night_hours`
   - `teff/minute` = `visits/hour * mean eff_time / 60`

---

## Function 2: `compute_smallsum`

### Signature

```python
def compute_smallsum(
    visits: pd.DataFrame,
    science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
) -> pd.DataFrame:
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `visits` | `pd.DataFrame` | A DataFrame of visits. Must contain columns: `dayObs`, `observationId`, `start_timestamp`, `eff_time_median`, `seeingFwhmGeom`, `airmass`, `HA`, `band`, `science_program`, `observation_reason`, `target_name`. |
| `science_programs` | `tuple[str, ...]` | Tuple of science_program values considered "science". Defaults to `SCIENCE_PROGRAMS` from `rubin_nights.reference_values`. |

### Returns

A `pd.DataFrame` with a two-level index: (`dayObs`, `subset`). Each night has multiple rows, one for each subset category. The `subset` level contains values like:
- `"all"` – aggregate of all visits that night
- `"science"`, `"not_science"` – split by whether `science_program` is in `science_programs`
- `"u"`, `"g"`, `"r"`, `"i"`, `"z"`, `"y"` – split by band
- observation_reason values – split by `observation_reason` column
- target name values – split by individual target names (with multi-target values exploded on `, `)

Columns of the returned DataFrame:

| Column | Type | Description |
|--------|------|-------------|
| `visits` | int | Number of visits in this subset |
| `first` | float | Earliest `start_timestamp` in this subset |
| `last` | float | Latest `start_timestamp` in this subset |
| `teff_total` | float | Sum of `eff_time_median` with NaN treated as 0 (total effective time) |
| `teff_q1` | float | 25th percentile of `eff_time_median` |
| `teff_median` | float | 50th percentile of `eff_time_median` |
| `teff_q3` | float | 75th percentile of `eff_time_median` |
| `fwhm_median` | float | Median `seeingFwhmGeom` |
| `airmass_median` | float | Median `airmass` |
| `HA_median` | float | Median hour angle |

### Implementation Steps

1. **Define a helper function `_visits_summary(visits_group)`** that takes a DataFrame (a group of visits) and returns a `pd.Series` with the columns listed above:
   ```
   visits      = len(visits_group)
   first       = visits_group.start_timestamp.min()
   last        = visits_group.start_timestamp.max()
   teff_total  = np.nan_to_num(visits_group.eff_time_median.to_numpy(), nan=0.0).sum()
   teff_q1     = visits_group.eff_time_median.quantile(0.25)
   teff_median = visits_group.eff_time_median.median()
   teff_q3     = visits_group.eff_time_median.quantile(0.75)
   fwhm_median = visits_group.seeingFwhmGeom.median()
   airmass_median = visits_group.airmass.median()
   HA_median   = visits_group.HA.median()
   ```

   Note: `teff_total` uses `np.nan_to_num` to treat NaN values as 0 before summing,
   rather than `mean * count`, so that nights with partial NaN data still produce
   a meaningful total.

2. **Full night ("all") subset**: Group `visits` by `dayObs`, apply `_visits_summary`. Add a column `subset = "all"`. Reset and set index to `(dayObs, subset)`.

3. **By band subset**: Group `visits` by `['dayObs', 'band']`, apply `_visits_summary`. Rename `band` index level to `subset`.

4. **By science subset**: Add a temporary column `science` = `"science"` if `science_program` in `science_programs`, else `"not_science"`. Group by `['dayObs', 'science']`, apply `_visits_summary`. Rename `science` index level to `subset`.

5. **By observation_reason subset**: Group by `['dayObs', 'observation_reason']`, apply `_visits_summary`. Rename `observation_reason` index level to `subset`.

6. **By target name subset**: Split `target_name` on `', '` and explode into multiple rows. Replace empty strings with `"no target name"`. Group by `['dayObs', 'target_names']`, apply `_visits_summary`. Rename `target_names` index level to `subset`.

7. **Concatenate** all five subset DataFrames. Sort by `dayObs` level (preserving order within each night).

---

## Helper Function (private)

```python
def _unique_targets(target_name_series: pd.Series) -> str:
```

Used by `compute_tinysum` to aggregate target names per night. Logic:
- Iterate over each value in the series
- Strip leading `ddf_` or `DDF ` prefix
- Split on `', '` to handle multi-target entries
- Collect all non-empty unique targets
- Return as a comma-separated string

---

## Dependencies

- `pandas`
- `numpy`
- `rubin_scheduler.site_models.Almanac` (for night duration in `compute_tinysum`)
- `rubin_nights.reference_values.SCIENCE_PROGRAMS` (default value for science program filtering)

---

## Notes

- Both functions are **pure computations**: they take a visits DataFrame and return a summary DataFrame. They do not read data from disk or network.
- The `visits` DataFrame is expected to already have the necessary columns populated (e.g., via stackers applied during collection).
- The `dayObs` column is expected to be an integer in YYYYMMDD format (as produced by `DayObsStacker`).
- The Almanac is only needed by `compute_tinysum` for the `night_hours` and rate columns. If these columns are not needed, the Almanac parameter can be set to `None` and those columns will be omitted.
- Integer count columns (`Total`, `science`, band counts) use pandas nullable `Int64` dtype to avoid float conversion when NaN values are present from joins.
- The `exp_time` column is required by `compute_tinysum` for the `mean eff_time/exp_time` normalized efficiency metric.
