"""Functions for creating nightly summary DataFrames from visits data.

This module provides two functions:

- ``compute_tinysum``: one row per night with key statistics.
- ``compute_smallsum``: multiple rows per night, broken out by subset
  (band, science/not-science, observation_reason, target name).
"""

__all__ = ["compute_tinysum", "compute_smallsum"]

from datetime import timedelta

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.site_models import Almanac

from schedview import DayObs

try:
    from rubin_nights.reference_values import SCIENCE_PROGRAMS
except ImportError:
    SCIENCE_PROGRAMS = ()

_BANDS: tuple[str, ...] = tuple(ModelObservatory(no_sky=True).bandlist)


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
) -> pd.DataFrame:
    """Create a one-row-per-night summary DataFrame from visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        DataFrame of visits. Must contain columns: ``dayObs`` (int,
        YYYYMMDD), ``observationId``, ``seeingFwhmGeom``,
        ``eff_time_median``, ``band``, ``science_program``,
        ``target_name``.
    science_programs : `tuple` [`str`], optional
        Tuple of ``science_program`` values considered science.
        Defaults to ``SCIENCE_PROGRAMS`` from
        ``rubin_nights.reference_values``.
    almanac : `Almanac` or `None`, optional
        A ``rubin_scheduler.site_models.Almanac`` instance used to
        compute night duration.
        Pass ``None`` to omit the ``night_hours``, ``visits/hour``,
        and ``teff/minute`` columns.

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
                "exp_time": "sum",
                "eff_time_median": "sum",
            }
        )
        .sort_index()
        .rename(
            columns={
                "observationId": "Total",
                "seeingFwhmGeom": "median FWHM",
                "exp_time": "total exp_time",
                "eff_time_median": "total eff_time",
            }
        )
    )
    basic_stats["Total"] = basic_stats["Total"].astype("Int64")

    teff_stats = (
        visits.groupby("dayObs")["eff_time_median"]
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

    science_visits = visits.loc[visits["science_program"].isin(science_programs), :]
    science_counts = science_visits.groupby("dayObs")["observationId"].count().rename("science").to_frame()

    targets = (
        science_visits.groupby("dayObs")["target_name"]
        .apply(_unique_targets)
        .rename("science targets")
        .to_frame()
    )

    tinysum = basic_stats.join([teff_stats, science_counts, band_counts, targets])

    tinysum["total eff_time/exp_time"] = tinysum["total eff_time"] / tinysum["total exp_time"]

    tinysum["science"] = tinysum["science"].fillna(0).astype("Int64")
    tinysum["science targets"] = tinysum["science targets"].fillna("")

    if almanac is not None:
        night_hours = _build_night_hours(almanac, tinysum.index)
        tinysum["night_hours"] = night_hours
        tinysum["visits/hour"] = tinysum["Total"] / tinysum["night_hours"]
        tinysum["teff/minute"] = tinysum["visits/hour"] * tinysum["mean eff_time"] / 60.0

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
