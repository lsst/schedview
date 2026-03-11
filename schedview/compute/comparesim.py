from functools import partial
from typing import Optional, Tuple

import astropy.units as u
import healpy as hp
import numpy as np
import pandas as pd
from astropy.coordinates import Angle, SkyCoord

from .multisim import fraction_common, match_visits_across_sims


def assign_field_hpids(
    simulated_visits: pd.DataFrame,
    completed_visits: pd.DataFrame,
    nside: int,
    coord_match_tolerance_deg: float,
    *,
    ra_col: str = "fieldRA",
    decl_col: str = "fieldDec",
    hpid_col: str = "fieldHpid",
    inplace: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Populate an id column for simulated and completed visits and
    propagate the id from the nearest simulated healpix to completed
    visits that lie within a specified angular tolerance.

    Parameters
    ----------
    simulated_visits : `pd.DataFrame`
        Simulated visit table; must contain columns identified by ``ra_col``
        and ``dec_col`` (both in degrees).  An integer column named
        ``hpid_col`` will be added or overwritten.

    completed_visits : `pd.DataFrame`
        Completed visit table; same column requirements as
        ``simulated_visits``.

    field_hpix_nside : `int`
        HEALPix nside that defines the pixel resolution.

    field_coord_tolerance_deg : `float`
        Maximum angular separation (deg) for a completed visit to be considered
        a match to a simulated healpix center.

    ra_col : str, optional, default ``"fieldRA"``
        Column name for right‑ascension values (degrees).

    dec_col : str, optional, default ``"fieldDec"``
        Column name for declination values (degrees).

    hpid_col : str, optional, default ``"fieldHpid"``
        Column name that will store the healpix index.

    inplace : bool, optional, default ``False``
        If ``True`` the input DataFrames are modified in place.  If ``False``
        (default) shallow copies are made so the originals stay untouched.

    Returns
    -------
    result : Tuple[pd.DataFrame, pd.DataFrame]
        ``(simulated_visits_out, completed_visits_out)`` the (possibly copied)
        DataFrames with the ``hpid_col`` column populated.
    """

    if not inplace:
        simulated_visits = simulated_visits.copy()
        completed_visits = completed_visits.copy()

    simulated_visits[hpid_col] = hp.ang2pix(
        nside=nside,
        theta=simulated_visits[ra_col],
        phi=simulated_visits[decl_col],
        lonlat=True,
    )

    # Values assigned here will be replaced by closest matches
    # in simulated_visit[hpid_col] if there are any within
    # field_coord_tolerance_deg
    completed_visits[hpid_col] = hp.ang2pix(
        nside=nside,
        theta=completed_visits[ra_col],
        phi=completed_visits[decl_col],
        lonlat=True,
    )

    # Find all hpids actually used in the simulation.
    sim_hpids = simulated_visits[hpid_col].unique()
    sim_hp_ra, sim_hp_dec = hp.pix2ang(nside=nside, ipix=sim_hpids, lonlat=True)
    sim_hp_coords = SkyCoord(ra=sim_hp_ra * u.deg, dec=sim_hp_dec * u.deg, frame="icrs")

    # Match completed visits to the nearest hpid actually used in simulations.
    completed_coords = SkyCoord(
        ra=completed_visits[ra_col].values * u.deg,
        dec=completed_visits[decl_col].values * u.deg,
        frame="icrs",
    )
    sim_hp_match_idx, sim_hp_sep, _ = completed_coords.match_to_catalog_sky(sim_hp_coords)

    # Apply tolerance mask and replace the healpix id where appropriate.
    within_tol = sim_hp_sep.deg < coord_match_tolerance_deg
    completed_visits.loc[within_tol, hpid_col] = sim_hpids[sim_hp_match_idx[within_tol]]

    return simulated_visits, completed_visits


def offsets_of_coord_band(sim_index: int, visits: pd.DataFrame, obs_index: int = 0) -> pd.DataFrame:
    """
    Compute the time offset between a set of observations and a
    single simulated visit ``sim_index`` for a given (fieldHpid, band)
    coordinate pair.

    Parameters
    ----------
    sim_index : int
        The simulation index to compare against the observation (index 0).
    visits : pd.DataFrame
        Table of visits that contains at least the columns *sim_index* and
        *start_timestamp*.

    Returns
    -------
    pd.DataFrame
        A DataFrame with columns ``obs_time``, ``sim_time`` and ``delta`` and
        an index level ``sim_index``.
    """

    offsets = match_visits_across_sims(visits.set_index("sim_index").start_timestamp, (obs_index, sim_index))

    # Normalize the order and sense of the offset
    if offsets.columns[0] == obs_index:
        offsets["delta"] = -1 * offsets["delta"]
    else:
        offsets = offsets[[obs_index, sim_index, "delta"]]

    assert offsets.columns[0] == obs_index
    assert offsets.columns[1] == sim_index
    assert offsets.columns[2] == "delta"
    assert len(offsets.columns) == 3
    offsets.columns = ["obs_time", "sim_time", "delta"]
    offsets["sim_index"] = sim_index
    offsets = offsets.set_index("sim_index")

    return offsets


def compute_obs_sim_offsets(
    visits: pd.DataFrame,
    obs_index: int = 0,
) -> pd.DataFrame:
    """
    Build a table of offsets for all simulated/completed pairs of visits.

    Parameters
    ----------
    visits : `pd.DataFrame`
        Table of visits with at least the columns ``sim_index``,
        ``fieldHpid`` and ``band``.
    obs_index : `int`, optional
        ``sim_index`` value for completed (observed) visits (default = 0).

    Returns
    -------
    sim_offsets : `pd.DataFrame`
        Offsets for every simulated visit, indexed by ``sim_index``,
        ``fieldHpid`` and ``band``.
    """
    sim_indexes = visits.sim_index.unique()
    sim_indexes = sim_indexes[sim_indexes != obs_index]

    offsets = pd.concat(
        visits.groupby(["fieldHpid", "band"]).apply(partial(offsets_of_coord_band, i)) for i in sim_indexes
    )
    offsets.index = offsets.index.reorder_levels(["sim_index", "fieldHpid", "band"])
    return offsets


def compute_offset_stats(
    offsets: pd.DataFrame,
    visits: Optional[pd.DataFrame] = None,
    hhmmss: bool = False,
) -> pd.DataFrame:
    """
    Produce a summary table of time offsets between completed and simulated
    visits.

    Parameters
    ----------
    offsets :  `pd.DataFrame`
        Result of :func:`compute_obs_sim_offsets`.  Must contain a ``delta``
        column and a ``sim_index`` level in the index.
    visits : `pd.DataFrame`, optional
        The original visits table, required only if observation counts or
        labels should be included in the returned ``DataFrame``.
    hhmmss : `bool`, optional
        If ``True``, convert the numeric statistics (mean, std, etc.) from
        seconds to an ``HH:MM:SS`` string representation.

    Returns
    -------
    offset_stats : `pd.DataFrame`
        A table where each row corresponds to a ``sim_index`` and columns
        include match counts, MAD, and the usual descriptive statistics.
    """
    abs_delta = np.abs(offsets["delta"])
    abs_delta.name = "abs_delta"

    offset_stats = offsets.groupby("sim_index")["delta"].describe()
    offset_stats.insert(0, "match count", offset_stats["count"].astype(int))
    offset_stats.insert(1, "MAD", abs_delta.to_frame().groupby("sim_index")["abs_delta"].median())

    if visits is not None:
        visit_counts = visits.groupby("sim_index").agg({"label": "count"})
        offset_stats.insert(
            0, "obs count", np.full_like(offset_stats["count"], visit_counts.loc[0]).astype(int)
        )
        offset_stats.insert(1, "sim count", visit_counts)
        offset_stats.insert(3, "#match/#obs", (offset_stats["count"] / offset_stats["obs count"]).round(2))
        offset_stats.insert(4, "#match/#sim", (offset_stats["count"] / offset_stats["sim count"]).round(2))

    offset_stats.drop(columns="count", inplace=True)

    if hhmmss:
        for column in ["MAD", "mean", "std", "min", "25%", "50%", "75%", "max"]:
            offset_stats.loc[:, column] = Angle(
                (offset_stats.loc[:, column].astype(int).values / 3600) * u.hour
            ).to_string(unit=u.hour, sep=":")

    if visits is not None and "label" in visits.columns:
        offset_stats.insert(0, "label", visits.groupby("sim_index")["label"].first().to_frame())

    return offset_stats


def compute_common_fractions(visit_counts: pd.DataFrame, sim_labels: pd.Series, obs_index: int = 0):
    fraction_obs_simulated = partial(fraction_common, visit_counts, sim2=obs_index, match_count=False)
    fraction_sim_observed = partial(fraction_common, visit_counts, obs_index, match_count=False)
    fraction_obs_simulated_num = partial(fraction_common, visit_counts, sim2=obs_index, match_count=True)
    fraction_sim_observed_num = partial(fraction_common, visit_counts, obs_index, match_count=True)

    sim_indexes = pd.Series(sim_labels.index.values[sim_labels.index.values != obs_index])
    fraction_completed = sim_labels.loc[sim_indexes, :].copy()
    fraction_completed["frac_obs_sim_num"] = sim_indexes.apply(fraction_obs_simulated_num).round(2).values
    fraction_completed["frac_sim_obs_num"] = sim_indexes.apply(fraction_sim_observed_num).round(2).values
    fraction_completed["frac_obs_sim"] = sim_indexes.apply(fraction_obs_simulated).round(2).values
    fraction_completed["frac_sim_obs"] = sim_indexes.apply(fraction_sim_observed).round(2).values
    return fraction_completed
