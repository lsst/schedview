import pandas as pd
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
        )
    else:
        if visit_source == "baseline":
            baseline_opsim_rp = ResourcePath(get_baseline())
        else:
            baseline_opsim_rp = ResourcePath(OPSIMDB_TEMPLATE.format(sim_version=visit_source))
        mjd: int = DayObs.from_date(day_obs).mjd
        visits = read_opsim(
            baseline_opsim_rp,
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

    ddf_field_names = tuple(ddf_locations().keys())
    # Different versions of the schedule include a DD: prefix, or not.
    # Catch them all.
    ddf_field_names = ddf_field_names + tuple([f"DD:{n}" for n in ddf_field_names])

    # Figure out which column has the target names.
    target_column_name = "target_name" if "target_name" in all_visits.columns else "target"
    if target_column_name not in all_visits.columns:
        raise ValueError("Cannot find a column in visits with which to identify DDF fields.")

    ddf_visits = all_visits.loc[all_visits[target_column_name].isin(ddf_field_names)]

    return ddf_visits
