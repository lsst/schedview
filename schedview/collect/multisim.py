import datetime
from typing import Any

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import ObservationArray, SchemaConverter

try:
    from rubin_sim.sim_archive import vseqarchive
    from rubin_sim.sim_archive.prenightindex import get_prenight_index

    HAVE_SIM_ARCHIVE = True
    MISSING_MODULE_ERROR = None
except ModuleNotFoundError as missing_module:
    HAVE_SIM_ARCHIVE = False
    MISSING_MODULE_ERROR = missing_module

from schedview import DayObs
from schedview.collect.visits import NIGHT_STACKERS
from schedview.compute.visits import add_coords_tuple


def read_multiple_prenights(
    sim_date: datetime.date | int | str | DayObs,
    day_obs: datetime.date | int | str | DayObs,
    stackers: list | None = NIGHT_STACKERS,
    **kwargs: Any,
):
    """Read results of multiple simulations for a time period from an archive.

    Parameters
    ----------
    sim_date : `datetime.date` or `int` or `str` or `DayObs`
        The date (dayobs) on which the simulations to be run.
    day_obs : `datetime.date` or `int` or `str` or `DayObs`
        The day_obs of the first night for which to load visits.
    stackers : `list` or `None`
        A list of stackers to apply.

    Returns
    -------
    visits : `pandas.DataFrame`
        Data on the visits.
    """
    assert HAVE_SIM_ARCHIVE, "Missing optional module " + MISSING_MODULE_ERROR.msg
    sim_date = DayObs.from_date(sim_date)
    assert isinstance(sim_date, DayObs)

    day_obs = DayObs.from_date(day_obs)
    assert isinstance(day_obs, DayObs)

    telescope = kwargs["telescope"] if "telescope" in kwargs else "simonyi"
    kwargs["telescope"] = "simonyi" if telescope.lower() in ("simonyi", "maintel") else "auxtel"
    assert telescope in ("simonyi", "auxtel")

    all_prenights_for_night = get_prenight_index(day_obs.date, **kwargs)
    sim_creation_day_obs = pd.to_datetime(all_prenights_for_night.sim_creation_day_obs).dt.date
    recent_prenight_mask = (sim_creation_day_obs >= sim_date.date).values
    prenights_for_night = all_prenights_for_night.loc[recent_prenight_mask, :].reset_index()
    if "visitseq_uuid" in prenights_for_night.columns:
        # If there are no simulations, the column won't exist, so only tryo to
        # make it the index if the corresponding column exists.
        prenights_for_night.set_index(["visitseq_uuid"], inplace=True)

    sim_metadata_keys = [
        "visitseq_label",
        "config_url",
        "scheduler_version",
        "sim_runner_kwargs",
        "sim_creation_day_obs",
        "daily_id",
        "tags",
    ]

    visits_list = []
    for visitseq_uuid, prenight_metadata in prenights_for_night.iterrows():
        these_visits = vseqarchive.get_visits(
            prenight_metadata["visitseq_url"],
            query=f"floor(observationStartMJD-0.5)=={day_obs.mjd}",
            stackers=stackers,
        )
        these_visits["visitseq_uuid"] = visitseq_uuid
        these_visits = add_coords_tuple(these_visits)

        for key in sim_metadata_keys:
            value = prenight_metadata[key] if key in prenight_metadata else None
            these_visits[key] = [value] * len(these_visits)

        visits_list.append(these_visits)

    if len(visits_list) > 0:
        visits = pd.concat(visits_list)
    else:
        # Make a DataFrame with the expected columns and no rows.
        visits = SchemaConverter().obs2opsim(ObservationArray()[0:0])
        visits["start_timestamp"] = pd.Series(dtype=np.dtype("<M8[ns]"))
        visits["daily_id"] = pd.Series(dtype=np.dtype("int64"))
        for key in sim_metadata_keys:
            if key in visits.columns:
                continue
            visits[key] = pd.Series()

    visits.rename(columns={"visitseq_label": "label", "daily_id": "sim_index"}, inplace=True)
    return visits
