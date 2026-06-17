import logging
import re
import warnings
from pathlib import Path

import pandas as pd
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_scheduler.utils import ddf_locations
from rubin_scheduler.utils.consdb import KNOWN_INSTRUMENTS
from rubin_sim import maf
from rubin_sim.data import get_baseline

from schedview import DayObs

from .consdb import read_consdb
from .opsim import read_opsim

logger = logging.getLogger(__name__)

# Use old-style format, because f-strings are not reusable
OPSIMDB_TEMPLATE = (
    "/sdf/group/rubin/web_data/sim-data/sims_featureScheduler_runs{sim_version}/baseline/"
    + "baseline_v{sim_version}_10yrs.db"
)

NIGHT_STACKERS = [
    maf.HourAngleStacker(),
    maf.stackers.ObservationStartDatetime64Stacker(),
    maf.stackers.ObservationStartTimestampStacker(),
    maf.stackers.OverheadStacker(),
    maf.stackers.HealpixStacker(),
    maf.stackers.DayObsStacker(),
    maf.stackers.DayObsMJDStacker(),
    maf.stackers.DayObsISOStacker(),
]

DDF_STACKERS = [
    maf.stackers.ObservationStartDatetime64Stacker(),
    maf.stackers.ObservationStartTimestampStacker(),
    maf.stackers.TeffStacker(filter_col="band"),
    maf.stackers.DayObsISOStacker(),
]

OLD_DDF_STACKERS = [
    maf.stackers.ObservationStartDatetime64Stacker(),
    maf.stackers.ObservationStartTimestampStacker(),
    maf.stackers.TeffStacker(filter_col="filter"),
    maf.stackers.DayObsISOStacker(),
]


def read_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    stackers: list[maf.stackers.base_stacker.BaseStacker] = [maf.stackers.ObservationStartTimestampStacker()],
    num_nights: int = 1,
    **kwargs,
) -> pd.DataFrame:
    """Read visits from a variety of possible sources.

    Parameters
    ----------
    day_obs : `str` or `int` or `DayObs`
        The night of observing as a dayobs.
    visit_source : `str`
        ``baseline`` to load from the current baseline, an instrument name
        to query the consdb, or a file name to load from an opsim output file.
        Values of known instruments are found in
        `rubin_scheduler.utils.consdb.KNOWN_INSTRUMENTS`.
    stackers : `list` of `maf.stackers.base_stacker.BaseStacker` subclasses
        The stackers to apply.
    num_nights : `int`
        The number of nights to loadp
    **kwargs
        Keyword arguments to be passed to `read_consdb`

    Returns
    -------
    visits : `pd.DataFrame`
        A `pd.DataFrame` of visits.

    """

    if visit_source in KNOWN_INSTRUMENTS:
        visits = read_consdb(
            visit_source,
            stackers=stackers,
            day_obs=DayObs.from_date(day_obs).date.isoformat(),
            num_nights=num_nights,
            **kwargs,
        )
    else:
        if visit_source == "baseline":
            # Special case of the current baseline.
            opsim_rp = ResourcePath(get_baseline())
        elif re.search(r"^(\d+\.)*\d+$", visit_source):
            # If the value was just a version # like 4.3.5 (or 4.3),
            # Map it into the appropriate file at USDF storage.
            opsim_rp = ResourcePath(OPSIMDB_TEMPLATE.format(sim_version=visit_source))
        else:
            # Read from whatever file is specified.
            opsim_rp = ResourcePath(visit_source)
        mjd: int = DayObs.from_date(day_obs).mjd
        visits = read_opsim(
            opsim_rp,
            constraint=f"FLOOR(observationStartMJD-0.5)<={mjd}"
            + f" AND FLOOR(observationStartMJD-0.5)>({mjd-num_nights})",
            stackers=stackers,
        )
    return visits


def read_ddf_visits(*args, **kwargs) -> pd.DataFrame:
    """Read DDF visits from a variety of possible sources.

    Parameters
    ----------
    day_obs : `str` or `int` or `DayObs`
        The night of observing as a dayobs.
    visit_source : `str`
        ``baseline`` to load from the current baseline, an instrument name
        to query the consdb, or a file name to load from an opsim output file.
        Values of known instruments are found in
        `rubin_scheduler.utils.consdb.KNOWN_INSTRUMENTS`.
    stackers : `list` of `maf.stackers.base_stacker.BaseStacker` subclasses
        The stackers to apply.
    num_nights : `int`
        The number of nights to loadp
    **kwargs
        Keyword arguments to be passed to `read_consdb`

    Returns
    -------
    visits : `pd.DataFrame`
        A `pd.DataFrame` of visits.

    """
    if "stackers" not in kwargs:
        kwargs["stackers"] = DDF_STACKERS

    all_visits = read_visits(*args, **kwargs)

    # Figure out which column has the target names.
    target_column_name = "target_name" if "target_name" in all_visits.columns else "target"
    if target_column_name not in all_visits.columns:
        raise ValueError("Cannot find a column in visits with which to identify DDF fields.")

    ddf_field_names = tuple(ddf_locations().keys())
    ddf_visits = []
    for ddf_name in ddf_field_names:
        matches_target_column = all_visits[target_column_name].str.contains(ddf_name, case=False)
        matches_note_column = all_visits["scheduler_note"].str.contains(f"DD:{ddf_name}", case=False)
        this_field_visits = all_visits.loc[matches_target_column | matches_note_column, :]

        # Add a column with just the DDF field name and nothing else,
        # so that if the same DDF appears in different places
        # in the target_name value they still get identified as the
        # same DDF field.
        this_field_visits["field_name"] = ddf_name
        ddf_visits.append(this_field_visits)
    ddf_visits = pd.concat(ddf_visits)

    return ddf_visits


def _is_cache_fresh(cache_path: Path) -> bool:
    """Determine whether a visits cache file is fresh enough to use.

    A cache file is considered fresh if it was last modified after yesterday's
    sunrise (i.e., after the last completed night ended) and before today's
    sunset (i.e., before tonight starts).  This window ensures the cached data
    is complete through the previous night and has not yet been superseded by
    new observations.

    Parameters
    ----------
    cache_path : `Path`
        Path to the cache file.

    Returns
    -------
    fresh : `bool`
        ``True`` if the file exists and its modification time falls within the
        freshness window, ``False`` otherwise.
    """
    if not cache_path.exists():
        return False

    cache_mtime = Time(cache_path.stat().st_mtime, format="unix")
    lower_bound = DayObs.from_date("yesterday").sunrise
    upper_bound = DayObs.from_date("today").sunset
    return lower_bound < cache_mtime < upper_bound


def cached_read_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    cache_dir: str | Path,
    stackers: list | None = None,
    ddf: bool = False,
) -> pd.DataFrame:
    """Read visits from a consdb source, using a local HDF5 cache when possible.

    On a cache hit (the cache file exists, is fresh, and was built with the
    same set of stackers), the cached data is read from disk and filtered to
    the requested ``day_obs``.  On a cache miss (file absent, stale, or built
    with different stackers), a full query is issued via
    `read_visits` / `read_ddf_visits`, the result is written back to the
    cache, and the filtered data is returned.

    The cache file is an HDF5 file with two keys:

    - ``"visits"`` — the full visits `~pandas.DataFrame` (all nights up to
      the query date).
    - ``"stackers"`` — a single-column `~pandas.DataFrame` (column
      ``"class_name"``) recording the fully-qualified class name of each
      stacker used to produce the cached data.  Used to detect stale caches
      caused by a change in the requested stacker set.

    Parameters
    ----------
    day_obs : `str` or `int` or `DayObs`
        The night of observing as a dayobs.  Visits up to and including this
        night are returned.
    visit_source : `str`
        A consdb instrument name (e.g. ``"lsstcam"``, ``"latiss"``).  Only
        sources in `~rubin_scheduler.utils.consdb.KNOWN_INSTRUMENTS` are
        supported; a `ValueError` is raised otherwise.
    cache_dir : `str` or `Path`
        Directory where cache files are stored.  Created automatically if it
        does not exist.
    stackers : `list` or ``None``, optional
        Stacker instances to apply when querying the source.  If ``None``,
        defaults to `NIGHT_STACKERS` (when ``ddf=False``) or
        ``DDF_STACKERS + [maf.stackers.DayObsStacker()]`` (when ``ddf=True``).
    ddf : `bool`, optional
        If ``True``, use `read_ddf_visits` instead of `read_visits` (filters
        results to DDF fields and uses DDF-appropriate stackers).

    Returns
    -------
    visits : `~pandas.DataFrame`
        Visits for nights up to and including ``day_obs``.

    Raises
    ------
    ValueError
        If ``visit_source`` is not a known consdb instrument.
    """
    if visit_source not in KNOWN_INSTRUMENTS:
        raise ValueError(
            f"cached_read_visits only supports consdb instruments "
            f"({', '.join(sorted(KNOWN_INSTRUMENTS))}), got {visit_source!r}."
        )

    # Resolve default stackers.
    if stackers is None:
        if ddf:
            stackers = DDF_STACKERS + [maf.stackers.DayObsStacker()]
        else:
            stackers = NIGHT_STACKERS

    cache_dir = Path(cache_dir)
    suffix = "_ddf" if ddf else ""
    cache_path = cache_dir / f"visits_{visit_source}{suffix}.h5"

    requested_class_names = {type(s).__module__ + "." + type(s).__qualname__ for s in stackers}
    day_obs_obj = DayObs.from_date(day_obs)

    # Attempt a cache hit.
    if _is_cache_fresh(cache_path):
        cached_class_names = set(pd.read_hdf(str(cache_path), key="stackers")["class_name"])

        if cached_class_names == requested_class_names:
            logger.debug("Reading visits from cache: %s", cache_path)
            all_visits = pd.read_hdf(str(cache_path), key="visits")
        else:
            logger.debug("Cache stacker mismatch, regenerating: %s", cache_path)
            all_visits = None
    else:
        logger.debug("Cache miss or stale, querying source: %s", visit_source)
        all_visits = None

    # Cache miss — query the source for all available history.
    if all_visits is None:
        fetch_kwargs = dict(stackers=stackers, num_nights=365 * 20)
        today = DayObs.from_date("today")
        if ddf:
            all_visits = read_ddf_visits(today, visit_source, **fetch_kwargs)
        else:
            all_visits = read_visits(today, visit_source, **fetch_kwargs)

        logger.debug("Writing visits cache: %s", cache_path)
        cache_dir.mkdir(parents=True, exist_ok=True)
        all_visits.to_hdf(str(cache_path), key="visits")
        pd.DataFrame({"class_name": sorted(requested_class_names)}).to_hdf(
            str(cache_path), key="stackers", append=True
        )

    # Filter to the requested day_obs.
    if "dayObs" not in all_visits.columns:
        warnings.warn(
            "The visits DataFrame does not have a 'dayObs' column; "
            "returning unfiltered data.  Add maf.stackers.DayObsStacker() "
            "to the stackers list to enable day_obs filtering.",
            UserWarning,
            stacklevel=2,
        )
        return all_visits
    return all_visits.loc[all_visits["dayObs"] <= day_obs_obj.yyyymmdd, :]
