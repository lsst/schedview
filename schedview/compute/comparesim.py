from functools import partial
from typing import Optional, Tuple

import astropy.units as u
import numpy as np
import numpy.typing as npt
import pandas as pd
from astropy.coordinates import Angle, SkyCoord

from .. import DECL_COL, POINTING_COL, RA_COL
from .multisim import match_visits_across_sims

# Static type checks can get confused by astropy units following
# the u.myunit idiom. Using u.Unit helps them.
DEG: u.Unit = u.Unit("deg")


def find_nearest_pointing_ids(
    ra: npt.NDArray[np.floating],
    decl: npt.NDArray[np.floating],
    pointing_ids: npt.NDArray[np.integer],
    pointing_ras: npt.NDArray[np.floating],
    pointing_decls: npt.NDArray[np.floating],
) -> Tuple[npt.NDArray[np.integer], npt.NDArray[np.floating]]:
    """Given arrays of input coordinates and associations of reference
    coordinates with ids, return the nearest ids to each input coordinate and
    their distances.

    Parameters
    ----------
    ra : `numpy.ndarray` of `float`
        Right ascension values of input coordinates in degrees.
    decl : `numpy.ndarray` of `float`
        Declination values of input coordinates in degrees.
    pointing_ids : `numpy.ndarray` of `int`
        Array of pointing IDs corresponding to the reference pointings.
    pointing_ras : `numpy.ndarray` of `float`
        Right ascension values of reference pointings in degrees.
    pointing_decls : `numpy.ndarray` of `float`
        Declination values of reference pointings in degrees.

    Returns
    -------
    matched_ids : `numpy.ndarray` of `int`
        Array of pointing IDs corresponding to the nearest pointings.
    match_separation : `numpy.ndarray` of `float`
        Array of angular separations in degrees between input coordinates
        and their nearest reference pointings.
    """

    input_coordinates = SkyCoord(ra, decl, unit="deg", frame="icrs")
    reference_coords = SkyCoord(pointing_ras, pointing_decls, unit="deg", frame="icrs")
    match_index, match_sep, _ = input_coordinates.match_to_catalog_sky(reference_coords)
    matched_ids = pointing_ids[match_index]
    return matched_ids, match_sep.deg


def combine_completed_with_sims(
    simulated_visits: pd.DataFrame,
    completed_visits: pd.DataFrame,
    scheduler_version: str,
    reference_pointings: pd.DataFrame | None = None,
    pointing_tolerance: float = 0.002,
) -> pd.DataFrame:
    """Combine a DataFrame of simulated visits with one of completed visits.

    Parameters
    ----------
    simulated_visits : `pd.DataFrame`
        DataFrame containing simulated visits, using the schema returned by
        `schedview.collect.multisim.read_multiple_prenights`. This schema
        includes columns mapped from the ``opsim`` outputs database, plus
        several additional columns including ``sim_index``, which identifies
        from which simulations each visit came.
    completed_visits : `pd.DataFrame`
        DataFrame containing completed (observed) visits, using the schema
        returned by `schedview.collect.visits.read_visits`. If reference
        pointings are used, columns must include columns designating R.A. and
        declination in decimal degrees, and named by `schedview.RA_COL` and
        `schedview.DECL_COL`.
    scheduler_version : `str`
        Version string of the scheduler used to generate the visits.
    reference_pointings : `pd.DataFrame` or `None`, optional
        DataFrame containing reference pointing coordinates for matching.
        If provided, completed visits will be matched to the nearest reference
        pointing. Default is None.
    pointing_tolerance : `float`, optional
        Tolerance in degrees for matching completed visits to reference
        pointings. Default is 0.002 degrees.

    Returns
    -------
    visits : `pd.DataFrame`
        Combined DataFrame of simulated and completed visits with most columns
        copied directly from their respective `pd.DataFrame` s of origin.
        The rows for the completed visits will be assigned (possibly dummy)
        values for ``sim_creation_day_obs``, ``config_url``, and
        ``sim_runner_kwargs``. ``label`` will be set to ``Completed`` for
        completed visits, and ``sim_index`` to 0. If reference pointings are
        provided, the column with the coordinate ID (specified by
        `schedview.POINTING_ID`) will be set to the closest available in
        the provided ``reference_pointings`` ``pd.DataFrame`` if there are
        any within ``pointing_tolerance``.
        (Otherwise, they are left unchanged.)
    """

    if 0 in simulated_visits.sim_index.values:
        raise ValueError(
            "Simulated visits must not include a sim_index of 0, "
            "because completed visits will be assign sim_index=0"
        )

    if len(completed_visits) > 0:
        completed_visits = completed_visits.copy()
        completed_visits["start_date"] = pd.to_datetime(
            completed_visits["start_date"], format="ISO8601"
        ).dt.tz_localize("UTC")
        completed_visits["filter"] = completed_visits["band"]
        completed_visits["sim_creation_day_obs"] = None
        completed_visits["sim_index"] = 0
        completed_visits["label"] = "Completed"
        completed_visits["config_url"] = ""
        completed_visits["scheduler_version"] = scheduler_version
        completed_visits["sim_runner_kwargs"] = {}
        completed_visits.loc[:, "tags"] = len(completed_visits) * [["completed"]]

        if reference_pointings is not None:
            nearest_pointing_id, match_separation = find_nearest_pointing_ids(
                completed_visits.loc[:, RA_COL].to_numpy(),
                completed_visits.loc[:, DECL_COL].to_numpy(),
                reference_pointings.index.to_numpy(),
                reference_pointings.loc[:, RA_COL].to_numpy(),
                reference_pointings.loc[:, DECL_COL].to_numpy(),
            )
            match_mask = match_separation < pointing_tolerance
            completed_visits.loc[match_mask, POINTING_COL] = nearest_pointing_id[match_mask]

        visits = pd.concat([completed_visits, simulated_visits])
    else:
        visits = simulated_visits.copy()

    return visits


def offsets_of_coord_band(sim_index: int, visits: pd.DataFrame, obs_index: int = 0) -> pd.DataFrame:
    """
    Compute the time offset between a set of observations and a
    single simulated visit ``sim_index`` for a given (fieldHpid, band)
    coordinate pair.

    Parameters
    ----------
    sim_index : `int`
        The simulation index to compare against the observation (index 0).
    visits : `pd.DataFrame`
        Table of visits that contains at least the columns ``sim_index`` and
        ``start_timestamp``.

    Returns
    -------
    offsets: `pd.DataFrame`
        A DataFrame with columns ``obs_time``, ``sim_time`` and ``delta`` and
        an index level ``sim_index``.
    """
    # This function is intended to be run on a DataFrame on a single
    # field/band combination, not on the whole set of visits, e.g. for a night.
    for col in ("band", POINTING_COL):
        if col in visits.columns:
            assert len(visits[col].unique()) == 1

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
    offsets.columns = pd.Index(data=["obs_time", "sim_time", "delta"])
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
        visits.groupby([POINTING_COL, "band"]).apply(partial(offsets_of_coord_band, i), include_groups=False)
        for i in sim_indexes
    )
    assert isinstance(offsets.index, pd.MultiIndex)
    offsets.index = offsets.index.reorder_levels(["sim_index", POINTING_COL, "band"])
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
