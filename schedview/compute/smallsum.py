"""Functions for creating nightly summary DataFrames from visits data.

This module provides two functions:

- ``compute_tinysum``: one row per night with key statistics.
- ``compute_smallsum``: multiple rows per night, broken out by subset
  (band, science/not-science, observation_reason, target name).
"""

__all__ = ["compute_tinysum", "compute_smallsum", "format_band_breakdown"]

from datetime import timedelta

import numpy as np
import pandas as pd
from rubin_scheduler.site_models import Almanac

from schedview import DayObs

try:
    from rubin_nights.reference_values import SCIENCE_PROGRAMS
except ImportError:
    SCIENCE_PROGRAMS = ()

_BANDS: tuple[str, ...] = tuple("ugrizy")


def _unique_targets(target_name_series: pd.Series) -> str:
    """Aggregate target names into a comma-separated string of unique values.

    Strips ``ddf_`` or ``DDF `` prefixes, splits multi-target entries on
    ``', '``, and returns a deduplicated comma-separated string.

    Parameters
    ----------
    target_name_series : `pandas.Series`
        Series of target_name values (strings) for a single night.

    Returns
    -------
    result : `str`
        Comma-separated unique target names.
    """
    targets: list[str] = []
    for value in target_name_series.dropna():
        if not isinstance(value, str):
            continue
        value = value.strip()
        if len(value) == 0:
            continue
        if value.startswith("ddf_") or value.startswith("DDF "):
            value = value[4:]
        for subtarget in value.split(", "):
            subtarget = subtarget.strip()
            if subtarget and subtarget not in targets:
                targets.append(subtarget)
    return ", ".join(targets)


def _build_night_hours(almanac: Almanac, dayobs_values: pd.Index) -> pd.Series:
    """Build a Series mapping dayObs (YYYYMMDD int) to night hours.

    Parameters
    ----------
    almanac : `Almanac`
        Almanac instance with sunset data.
    dayobs_values : `pandas.Index`
        The dayObs index values for which to compute night hours.

    Returns
    -------
    night_hours : `pandas.Series`
        Series indexed by dayObs with night duration in hours.
    """
    sunsets = pd.DataFrame(almanac.sunsets)
    night0 = sunsets[sunsets["night"] == 0]
    if night0.empty:
        raise ValueError("Almanac.sunsets has no night 0; cannot compute night hours.")
    start_date = DayObs.from_time(night0.iloc[0]["sunset"]).date

    sunsets["dayObs"] = [
        int((start_date + timedelta(days=int(n))).strftime("%Y%m%d")) for n in sunsets["night"]
    ]
    sunsets = sunsets.set_index("dayObs")
    night_hours = (sunsets["sun_n12_rising"] - sunsets["sun_n12_setting"]) * 24.0
    return night_hours.reindex(dayobs_values)


def format_band_breakdown(row: pd.Series, prefix: str = "# ", suffix: str = "") -> str:
    """Format a per-band visit-count breakdown like ``500g, 170r, 6i``.

    Parameters
    ----------
    row : `pandas.Series`
        A single ``compute_tinysum`` row (e.g. ``tinysum.loc[dayobs]``).
    prefix : `str`, optional
        Text before the band name in the column label. Defaults to ``"# "``.
    suffix : `str`, optional
        Text after the band name in the column label. The count for band
        ``b`` is read from ``row[f"{prefix}{b}{suffix}"]``. The defaults
        select the total band columns (``# g`` ...); pass ``suffix=" science"``
        to select the science band columns (``# g science`` ...).

    Returns
    -------
    breakdown : `str`
        Comma-separated ``{count}{band}`` pairs for bands with a nonzero
        count, in ``_BANDS`` order. Empty string if every count is zero or
        absent.
    """
    parts = []
    for band in _BANDS:
        column = f"{prefix}{band}{suffix}"
        if column not in row.index:
            continue
        count = row[column]
        if pd.isna(count) or int(count) == 0:
            continue
        parts.append(f"{int(count)}{band}")
    return ", ".join(parts)


def _visits_summary(visits_group: pd.DataFrame) -> pd.Series:
    """Compute summary statistics for a group of visits.

    Parameters
    ----------
    visits_group : `pandas.DataFrame`
        A subset of visits (one group from a groupby operation).

    Returns
    -------
    summary : `pandas.Series`
        Series with keys: visits, first, last, teff_total, teff_q1,
        teff_median, teff_q3, fwhm_median, airmass_median, HA_median.
    """
    teff = visits_group["eff_time_median"]
    return pd.Series(
        {
            "visits": len(visits_group),
            "first": visits_group["start_timestamp"].min(),
            "last": visits_group["start_timestamp"].max(),
            "teff_total": np.nan_to_num(teff.to_numpy(), nan=0.0).sum(),
            "teff_q1": teff.quantile(0.25),
            "teff_median": teff.median(),
            "teff_q3": teff.quantile(0.75),
            "fwhm_median": visits_group["seeingFwhmGeom"].median(),
            "airmass_median": visits_group["airmass"].median(),
            "HA_median": visits_group["HA"].median(),
        }
    )


def compute_tinysum(
    visits: pd.DataFrame,
    science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
    almanac: Almanac | None = None,
    eff_time_column: str = "eff_time_median",
    exp_time_column: str = "exp_time",
    all_science: bool = False,
) -> pd.DataFrame:
    """Create a one-row-per-night summary DataFrame from visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        DataFrame of visits. Must contain columns: ``dayObs`` (int,
        YYYYMMDD), ``observationId``, ``seeingFwhmGeom``, the
        effective-time column named by ``eff_time_column``, the
        exposure-time column named by ``exp_time_column``, ``band``,
        ``science_program``, ``target_name``.
    science_programs : `tuple` [`str`], optional
        Tuple of ``science_program`` values considered science.
        Defaults to ``SCIENCE_PROGRAMS`` from
        ``rubin_nights.reference_values``.
    almanac : `Almanac` or `None`, optional
        A ``rubin_scheduler.site_models.Almanac`` instance used to
        compute night duration.
        Pass ``None`` to omit the ``night_hours``, ``visits/hour``,
        and ``teff/night duration`` columns.
    eff_time_column : `str`, optional
        Name of the per-visit effective-time column in ``visits``.
        Defaults to ``"eff_time_median"`` (the consdb/production name).
        Pass ``"t_eff"`` for prenight-simulation visits, which carry the
        same statistic under a different name.
    exp_time_column : `str`, optional
        Name of the per-visit exposure-time column in ``visits``.
        Defaults to ``"exp_time"`` (the consdb/production name). Pass
        ``"visitExposureTime"`` for prenight-simulation visits.
    all_science : `bool`, optional
        If ``True``, treat every visit as a science visit regardless of
        its ``science_program``, so the science counts equal the totals.
        Defaults to ``False``.  Pass ``True`` for prenight-simulation
        visits, which contain only science visits.

    Returns
    -------
    tinysum : `pandas.DataFrame`
        DataFrame indexed by ``dayObs`` with one row per night.
    """
    basic_stats = (
        visits.groupby("dayObs")
        .agg(
            {
                "observationId": "count",
                "seeingFwhmGeom": "median",
                exp_time_column: "sum",
                eff_time_column: "sum",
            }
        )
        .sort_index()
        .rename(
            columns={
                "observationId": "Total",
                "seeingFwhmGeom": "median FWHM",
                exp_time_column: "total exp_time",
                eff_time_column: "total eff_time",
            }
        )
    )
    basic_stats["Total"] = basic_stats["Total"].astype("Int64")

    teff_stats = (
        visits.groupby("dayObs")[eff_time_column]
        .describe()
        .loc[:, ["mean", "25%", "50%", "75%"]]
        .rename(
            columns={
                "mean": "mean eff_time",
                "25%": "q1 eff_time",
                "50%": "median eff_time",
                "75%": "q3 eff_time",
            }
        )
    )

    band_counts = (
        visits.groupby(["dayObs", "band"])["observationId"]
        .count()
        .unstack("band", fill_value=0)
        .reindex(columns=_BANDS, fill_value=0)
        .astype("Int64")
        .rename(columns={b: f"# {b}" for b in _BANDS})
    )

    if all_science:
        science_visits = visits
    else:
        science_visits = visits.loc[visits["science_program"].isin(science_programs), :]
    science_counts = science_visits.groupby("dayObs")["observationId"].count().rename("science").to_frame()

    science_band_counts = (
        science_visits.groupby(["dayObs", "band"])["observationId"]
        .count()
        .unstack("band", fill_value=0)
        .reindex(columns=_BANDS, fill_value=0)
        .astype("Int64")
        .rename(columns={b: f"# {b} science" for b in _BANDS})
    )

    targets = (
        science_visits.groupby("dayObs")["target_name"]
        .apply(_unique_targets)
        .rename("science targets")
        .to_frame()
    )

    tinysum = basic_stats.join([teff_stats, science_counts, band_counts, science_band_counts, targets])

    tinysum["total eff_time/total exp_time"] = tinysum["total eff_time"] / tinysum["total exp_time"]

    # Effective-time breakdown factors (only if all three columns present)
    _EFF_TIME_FACTOR_MAP = {
        "eff_time_psf_sigma_scale_median": "eff_time_psf_scale",
        "eff_time_zero_point_scale_median": "eff_time_zp_scale",
        "eff_time_sky_bg_scale_median": "eff_time_skybg_scale",
    }
    if all(col in visits.columns for col in _EFF_TIME_FACTOR_MAP):
        exp_by_night = visits[exp_time_column].groupby(visits["dayObs"]).sum()
        for input_col, output_col in _EFF_TIME_FACTOR_MAP.items():
            weighted = (visits[input_col] * visits[exp_time_column]).groupby(visits["dayObs"]).sum()
            tinysum[output_col] = weighted / exp_by_night

    tinysum["science"] = tinysum["science"].fillna(0).astype("Int64")
    science_band_cols = [f"# {b} science" for b in _BANDS]
    tinysum[science_band_cols] = tinysum[science_band_cols].fillna(0).astype("Int64")
    tinysum["science targets"] = tinysum["science targets"].fillna("")

    if almanac is not None:
        night_hours = _build_night_hours(almanac, tinysum.index)
        tinysum["night_hours"] = night_hours
        tinysum["visits/hour"] = tinysum["Total"] / tinysum["night_hours"]
        tinysum["teff/night duration"] = tinysum["total eff_time"] / (tinysum["night_hours"] * 60 * 60)

    return tinysum


def compute_smallsum(
    visits: pd.DataFrame,
    science_programs: tuple[str, ...] = SCIENCE_PROGRAMS,
) -> pd.DataFrame:
    """Create a multi-row-per-night summary DataFrame from visits.

    Each night has rows for several subsets: all visits, by band,
    science/not-science, by observation_reason, and by target name.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        DataFrame of visits. Must contain columns: ``dayObs``,
        ``observationId``, ``start_timestamp``, ``eff_time_median``,
        ``seeingFwhmGeom``, ``airmass``, ``HA``, ``band``,
        ``science_program``, ``observation_reason``, ``target_name``.
    science_programs : `tuple` [`str`], optional
        Tuple of ``science_program`` values considered science.
        Defaults to ``SCIENCE_PROGRAMS`` from
        ``rubin_nights.reference_values``.

    Returns
    -------
    smallsum : `pandas.DataFrame`
        DataFrame with a two-level index (``dayObs``, ``subset``).
    """
    fullnight = visits.groupby("dayObs").apply(_visits_summary, include_groups=False)
    fullnight["subset"] = "all"
    fullnight = fullnight.reset_index().set_index(["dayObs", "subset"])

    byband = visits.groupby(["dayObs", "band"]).apply(_visits_summary, include_groups=False)
    byband = byband.rename_axis(index={"band": "subset"})

    visits_with_science = visits.copy()
    visits_with_science["_science"] = np.where(
        visits_with_science["science_program"].isin(science_programs),
        "science",
        "not_science",
    )
    byscience = visits_with_science.groupby(["dayObs", "_science"]).apply(
        _visits_summary, include_groups=False
    )
    byscience = byscience.rename_axis(index={"_science": "subset"})

    byreason = visits.groupby(["dayObs", "observation_reason"]).apply(_visits_summary, include_groups=False)
    byreason = byreason.rename_axis(index={"observation_reason": "subset"})

    visits_with_targets = visits.copy()
    visits_with_targets["_target_names"] = (
        visits_with_targets["target_name"].fillna("").astype(str).str.split(", ")
    )
    bytarget = visits_with_targets.explode("_target_names")
    bytarget["_target_names"] = bytarget["_target_names"].fillna("").str.strip()
    bytarget.loc[bytarget["_target_names"] == "", "_target_names"] = "no target name"
    bytarget = bytarget.groupby(["dayObs", "_target_names"]).apply(_visits_summary, include_groups=False)
    bytarget = bytarget.rename_axis(index={"_target_names": "subset"})

    smallsum = pd.concat([fullnight, byband, byscience, byreason, bytarget])
    smallsum = smallsum.sort_index(level="dayObs", sort_remaining=False)
    return smallsum
