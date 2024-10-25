from warnings import warn

import pandas as pd
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_scheduler.utils import ddf_locations
from rubin_sim import maf

from schedview import DayObs

from .consdb import read_consdb
from .opsim import read_ddf_visits as read_ddf_visits_from_opsim
from .opsim import read_opsim

KNOWN_INSTRUMENTS = ["lsstcomcamsim"]

# Use old-style format, because f-strings are not reusable
OPSIMDB_TEMPLATE = (
    "/sdf/group/rubin/web_data/sim-data/sims_featureScheduler_runs{sim_version}/baseline/"
    + "baseline_v{sim_version}_10yrs.db"
)

NIGHT_STACKERS = [
    maf.HourAngleStacker(),
    maf.stackers.ObservationStartDatetime64Stacker(),
    maf.stackers.TeffStacker(),
    maf.stackers.OverheadStacker(),
]

DDF_STACKERS = [
    maf.stackers.ObservationStartDatetime64Stacker(),
    maf.stackers.TeffStacker(),
    maf.stackers.DayObsISOStacker(),
]


def read_night_visits(
    day_obs: str | int | DayObs,
    visit_source: str,
    stackers: list[maf.stackers.base_stacker.BaseStacker] = [],
) -> pd.DataFrame:

    if visit_source in KNOWN_INSTRUMENTS:
        visits = read_consdb(
            visit_source, stackers=stackers, day_obs=DayObs.from_date(day_obs).date.isoformat()
        )
    else:
        baseline_opsim_rp = ResourcePath(OPSIMDB_TEMPLATE.format(sim_version=visit_source))
        mjd = DayObs.from_date(day_obs).mjd
        visits = read_opsim(
            baseline_opsim_rp,
            constraint=f"FLOOR(observationStartMJD-0.5)={mjd}",
            stackers=stackers,
        )
    return visits


def read_ddf_visits(
    day_obs: str | int | DayObs,
    visits: pd.DataFrame,
    previous_source: str = "",
    time_window_duration: int = 90,
    stackers: list[maf.stackers.base_stacker.BaseStacker] = [],
) -> pd.DataFrame:

    mjd = DayObs.from_date(day_obs).mjd
    start_time = Time(mjd - time_window_duration - 0.5, format="mjd")
    end_time = Time(mjd + 0.5, format="mjd")

    ddf_field_names = tuple(ddf_locations().keys())

    # Figure out which column has the target names.
    target_column_name = "target_name" if "target_name" in visits.columns else "target"
    if target_column_name in visits.columns:
        visits_dfs = [visits.loc[visits[target_column_name].isin(ddf_field_names)]]
    else:
        warn("Cannot find a column in visits with which to identify DDF fields.")
        visits_dfs = []

    if previous_source:
        visits_dfs.insert(
            0,
            read_ddf_visits_from_opsim(
                previous_source, start_time=start_time, end_time=end_time, stackers=stackers
            ),
        )

    ddf_visits = pd.concat(visits_dfs)

    return ddf_visits
