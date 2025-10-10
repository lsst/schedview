from datetime import date

import pandas as pd
from lsst.resources import ResourcePath
from rubin_sim.sim_archive.vseqmetadata import VisitSequenceArchiveMetadata

from schedview import DayObs

MAX_AGE = 365


def get_prenight_index_from_database(
    day_obs: str | int | date | DayObs,
    telescope: str = "simonyi",
    schema: str | None = None,
    host: str | None = None,
    user: str | None = None,
    database: str | None = None,
) -> pd.DataFrame:

    day_obs = DayObs.from_date(day_obs)
    assert isinstance(day_obs, DayObs)
    metadata_dsn = {}
    if host is not None:
        metadata_dsn["host"] = host
    if user is not None:
        metadata_dsn["user"] = user
    if database is not None:
        metadata_dsn["database"] = database

    visit_seq_archive_metadata = VisitSequenceArchiveMetadata(metadata_dsn, schema)
    prenights = visit_seq_archive_metadata.sims_on_nights(
        day_obs.date, day_obs.date, tags=["prenight"], telescope=telescope, max_simulation_age=MAX_AGE
    ).set_index("visitseq_uuid")
    return prenights


def get_prenight_index_from_bucket(
    day_obs: str | int | date | DayObs,
    telescope: str = "simonyi",
    prenight_index_path: (
        str | ResourcePath
    ) = "s3://rubin:rubin-scheduler-prenight/opsim/test/prenight_index/",
) -> pd.DataFrame:

    day_obs = DayObs.from_date(day_obs)
    assert isinstance(day_obs, DayObs)

    prenight_index_path = ResourcePath(prenight_index_path, forceDirectory=True)
    assert isinstance(prenight_index_path, ResourcePath)

    year = day_obs.date.year
    month = day_obs.date.month
    isodate = str(day_obs)

    prenight_index_resource_path = (
        prenight_index_path.join(telescope)
        .join(str(year))
        .join(str(month))
        .join(f"{telescope}_prenights_for_{isodate}.json")
    )
    with prenight_index_resource_path.as_local() as local_resource_path:
        prenights = pd.read_json(local_resource_path.ospath, orient="index")

    return prenights
