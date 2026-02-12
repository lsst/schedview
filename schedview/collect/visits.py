import re

import astropy.units as u
import pandas as pd
from astropy.coordinates import SkyCoord, search_around_sky
from lsst.resources import ResourcePath
from rubin_scheduler.utils import ddf_locations
from rubin_scheduler.utils.consdb import KNOWN_INSTRUMENTS
from rubin_sim import maf
from rubin_sim.data import get_baseline

from schedview import DayObs

from .consdb import read_consdb
from .opsim import read_opsim

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


def match_visits_to_pointings(
    visits: pd.DataFrame,
    pointings: dict,
    ra_col: str = "s_ra",
    decl_col: str = "s_dec",
    name_col: str = "pointing_name",
    match_radius: float = 1.75,
) -> pd.DataFrame:
    """Match visits to pointings based on coordinates.

    Parameters
    ----------
    visits : `pd.DataFrame`
        DataFrame containing visit data with equatorial coordinates.
    pointings : `dict`
        Dictionary of pointings where keys are pointing names and values are
        coordinate tuples (ra, dec) in degrees.
    ra_col : `str`, optional
        Name of the column containing right ascension values in the visits DataFrame.
        Default is "s_ra".
    decl_col : `str`, optional
        Name of the column containing declination values in the visits DataFrame.
        Default is "s_dec".
    name_col : `str`, optional
        Name of the column to be added to the output DataFrame to identify
        which pointing each visit matches to. Default is "pointing_name".
    match_radius : `float`, optional
        Matching radius in degrees for associating visits with pointings.
        Default is 1.75 degrees.

    Returns
    -------
    pointing_visits : `pd.DataFrame`
        DataFrame containing the original visits DataFrame with an additional column
        (named by ``name_col``) identifying which pointing each visit matches to.
        The returned DataFrame maintains the original visit data but is filtered
        to only include visits that match to at least one pointing.

    """

    pointings_df = pd.DataFrame(pointings).T
    pointings_df.columns = pd.Index(["ra", "decl"])
    pointing_coords = SkyCoord(
        ra=pointings_df.ra.values * u.deg, dec=pointings_df.decl.values * u.deg, frame="icrs"
    )

    visit_centers = SkyCoord(
        ra=visits[ra_col].values * u.deg, dec=visits[decl_col].values * u.deg, frame="icrs"
    )

    pointing_matches = search_around_sky(pointing_coords, visit_centers, match_radius * u.deg)

    visit_match_dfs = {}
    for pointing_idx, pointing_name in enumerate(pointings):
        visit_idx = pointing_matches[1][pointing_matches[0] == pointing_idx]
        visit_match_dfs[pointing_name] = visits.iloc[visit_idx, :].copy()
        visit_match_dfs[pointing_name][name_col] = pointing_name

    pointing_visits = pd.concat([visit_match_dfs[n] for n in visit_match_dfs])

    return pointing_visits
