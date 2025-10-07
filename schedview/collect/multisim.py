import datetime
from typing import Literal

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import ObservationArray, SchemaConverter
from rubin_sim.sim_archive import vseqarchive
from rubin_sim.sim_archive.vseqmetadata import VisitSequenceArchiveMetadata

from schedview import DayObs
from schedview.collect.visits import NIGHT_STACKERS
from schedview.compute.visits import add_coords_tuple


def read_multiple_prenights(
    vsarch: VisitSequenceArchiveMetadata,
    sim_date: datetime.date | int | str | DayObs,
    day_obs: datetime.date | int | str | DayObs,
    stackers: list | None = NIGHT_STACKERS,
    telescope: Literal["AuxTel", "Simonyi", "auxtel", "simonyi", "maintel"] = "simonyi",
):
    """Read results of multiple simulations for a time period from an archive.

    Parameters
    ----------
    vsarch : `VisitSequencArchiveMetadata`
        The interface to the visit sequence archive metadata.
    sim_date : `datetime.date` or `int` or `str` or `DayObs`
        The date (dayobs) on which the simulations to be run.
    day_obs_mjd : `datetime.date` or `int` or `str` or `DayObs`
        The day_obs of the first night for which to load visits.
    stackers : `list` or `None`
        A list of stackers to apply.
    telescope : `str`
        The telescope te read simulations for (Simonyi or Auxtel)

    Returns
    -------
    visits : `pandas.DataFrame`
        Data on the visits.
    """
    sim_date = DayObs.from_date(sim_date)
    assert isinstance(sim_date, DayObs)

    day_obs = DayObs.from_date(day_obs)
    assert isinstance(day_obs, DayObs)

    telescope = "simonyi" if telescope.lower() in ("simonyi", "maintel") else "auxtel"
    assert telescope in ("simonyi", "auxtel")

    max_age = (datetime.date.today() - sim_date.date).days + 1
    prenights_for_night = vsarch.sims_on_nights(
        day_obs.date, day_obs.date, tags=["prenight"], telescope=telescope, max_simulation_age=max_age
    ).set_index(["visitseq_uuid"])

    visits_list = []
    for visitseq_uuid, prenight_metadata in prenights_for_night.iterrows():
        these_visits = vseqarchive.get_visits(
            prenight_metadata["visitseq_url"],
            query=f"floor(observationStartMJD-0.5)=={day_obs.mjd}",
            stackers=stackers,
        )
        these_visits["visitseq_uuid"] = visitseq_uuid
        these_visits = add_coords_tuple(these_visits)

        sim_metadata_keys = [
            "visitseq_label",
            "config_url",
            "schedulre_version",
            "sim_runner_kwargs",
            "sim_creation_day_obs",
            "daily_id",
            "tags",
        ]
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
