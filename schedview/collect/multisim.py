from typing import Literal

import astropy
import astropy.time
import numpy as np
import pandas as pd
import rubin_sim
from lsst.resources import ResourcePath
from rubin_scheduler.scheduler.utils import ObservationArray, SchemaConverter

from ..collect.visits import NIGHT_STACKERS
from ..compute.visits import add_coords_tuple
from .opsim import all_visits_columns, read_opsim


def read_multiple_opsims(
    archive_uri: str,
    sim_date: str,
    day_obs_mjd: int,
    stackers: list | None = NIGHT_STACKERS,
    telescope: Literal["AuxTel", "Simonyi", "auxtel", "simonyi", "maintel"] = "simonyi",
):
    """Read results of multiple simulations for a time period from an archive.

    Parameters
    ----------
    archive_uri : `str`
        The URI of the sim archive.
    sim_date : `str`
        The date on which the simulations to be run.
    day_obs_mjd : `int`
        The day_obs MJD of the first night for which to load visits.
    stackers : `list` or `None`
        A list of stackers to apply.
    telescope : `str`
        The telescope te read simulations for (Simonyi or Auxtel)

    Returns
    -------
    visits : `pandas.DataFrame`
        Data on the visits.
    """

    telescope = "simonyi" if telescope.lower() in ("simonyi", "maintel") else "auxtel"
    assert telescope in ("simonyi", "auxtel")

    sims_metadata = rubin_sim.sim_archive.read_archived_sim_metadata(
        archive_uri, latest=sim_date, num_nights=1
    )

    visits_list = []
    for sim_uri, sim_metadata in sims_metadata.items():
        if "telescope" not in sim_metadata or sim_metadata["telescope"] != telescope:
            # This sim is for the wrong telescope, so skip it.
            continue

        version_key = (
            "opsim_config_version" if "opsim_config_version" in sim_metadata else "opsim_config_branch"
        )
        sim_metadata_keys = [
            "label",
            version_key,
            "opsim_config_repository",
            "opsim_config_script",
            "scheduler_version",
            "sim_runner_kwargs",
            "tags",
        ]

        first_day_obs_mjd = astropy.time.Time(sim_metadata["simulated_dates"]["first"]).mjd
        last_day_obs_mjd = astropy.time.Time(sim_metadata["simulated_dates"]["last"]).mjd

        # Make mypy happy
        assert isinstance(first_day_obs_mjd, float)
        assert isinstance(last_day_obs_mjd, float)

        includes_day_obs = first_day_obs_mjd <= day_obs_mjd <= last_day_obs_mjd

        if not includes_day_obs:
            continue

        sim_rp = ResourcePath(sim_uri).join(sim_metadata["files"]["observations"]["name"])

        these_visits = read_opsim(
            sim_rp,
            constraint=f"FLOOR(observationStartMJD-0.5)={day_obs_mjd}",
            stackers=stackers,
            dbcols=all_visits_columns(),
        )
        these_visits = add_coords_tuple(these_visits)
        these_visits["sim_date"] = sim_uri.split("/")[-3]
        these_visits["sim_index"] = int(sim_uri.split("/")[-2])

        for key in sim_metadata_keys:
            value = sim_metadata[key] if key in sim_metadata else None
            these_visits[key] = [value] * len(these_visits)

        visits_list.append(these_visits)

    if len(visits_list) > 0:
        visits = pd.concat(visits_list)
    else:
        # Make a DataFrame with the expected columns and no rows.
        visits = SchemaConverter().obs2opsim(ObservationArray()[0:0])
        visits["start_timestamp"] = pd.Series(dtype=np.dtype("<M8[ns]"))
        visits["sim_index"] = pd.Series(dtype=np.dtype("int64"))
        expected_sim_metadata_keys = [
            "sim_date",
            "label",
            "opsim_config_version",
            "opsim_config_repository",
            "opsim_config_script",
            "scheduler_version",
            "sim_runner_kwargs",
            "tags",
        ]
        for key in expected_sim_metadata_keys:
            visits[key] = pd.Series()
    return visits
