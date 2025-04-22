from collections import OrderedDict

import astropy.units as u
import numpy as np
from astropy.time import Time, TimezoneInfo
from lsst.resources import ResourcePath

from schedview import DayObs


def munge_sim_archive_metadata(sim_metadata, day_obs, archive_uri):
    """Normalize simulation metadata returned from the simulation archive.

    Parameters
    ----------
    sim_metadata : `dict`
       Simulation metadata returned by the simulation archive as a dictionary
       of dictionaries, as storted in the metadata archive.
    day_obs : `DayObs` or `str`
        The night of observing.
    archive_uri : `str`
        The URI of the simulation archive.

    Returns
    -------
    sim_metadata : `dict`
        A dictionary of dictionaries with keys and their meanings updated
        to match a uniform schema.
    """
    # Whatever form we get it in, turn it into a YYYY-MM-DD string.
    day_obs = str(DayObs.from_date(day_obs))
    # Let mypy know we've done that.
    assert isinstance(day_obs, str)

    marked_for_deletion = []
    for sim_uri in sim_metadata:
        try:
            first_day_obs = sim_metadata[sim_uri]["simulated_dates"]["first_day_obs"]
            last_day_obs = sim_metadata[sim_uri]["simulated_dates"]["last_day_obs"]
        except KeyError:
            try:
                first_time = sim_metadata[sim_uri]["simulated_dates"]["first"]
                if len(first_time) == 10:
                    # If the length is 10, it's really a date.
                    first_day_obs = first_time
                else:
                    # day_obs is in utc-12 hours, but opsim starts in UTC
                    first_day_obs = (
                        Time(first_time)
                        .to_datetime(timezone=TimezoneInfo(utc_offset=-12 * u.hour))
                        .date()
                        .isoformat()
                    )
                sim_metadata[sim_uri]["simulated_dates"]["first_day_obs"] = first_day_obs

                last_time = sim_metadata[sim_uri]["simulated_dates"]["last"]
                if len(last_time) == 10:
                    # If the length is 10, it's really a date.
                    last_day_obs = last_time
                else:
                    # day_obs is in utc-12 hours, but opsim starts in UTC
                    last_day_obs = (
                        Time(last_time)
                        .to_datetime(timezone=TimezoneInfo(utc_offset=-12 * u.hour))
                        .date()
                        .isoformat()
                    )

                sim_metadata[sim_uri]["simulated_dates"]["last_day_obs"] = last_day_obs
            except KeyError:
                marked_for_deletion.append(sim_uri)
                continue

        if first_day_obs <= day_obs <= last_day_obs:
            this_sim_rp = ResourcePath(sim_uri)
            archives_resource_path = ResourcePath(archive_uri)
            date_str, index_str = this_sim_rp.relative_to(archives_resource_path).split("/")
            if "sim_execution_date" not in sim_metadata[sim_uri]:
                sim_metadata[sim_uri]["sim_execution_date"] = date_str
            if "sim_index" not in sim_metadata[sim_uri]:
                sim_metadata[sim_uri]["sim_index"] = int(index_str)
            sim_metadata[sim_uri]["files"]["observations"]["url"] = this_sim_rp.join(
                sim_metadata[sim_uri]["files"]["observations"]["name"]
            )
            sim_metadata[sim_uri]["simulated_dates"]["first_day_obs"] = first_day_obs

        else:
            marked_for_deletion.append(sim_uri)

    for out_of_range_uri in marked_for_deletion:
        del sim_metadata[out_of_range_uri]

    # Sort the simulations, most recent first.
    sort_by_values = np.array(
        [(s["sim_execution_date"], s["sim_index"], s["label"]) for s in sim_metadata.values()],
        dtype=[("date", np.str_, 10), ("id", int), ("label", np.str_, 128)],
    )
    descending_indexes = np.flip(sort_by_values.argsort())
    sim_metadata = OrderedDict(
        (list(sim_metadata.keys())[i], sim_metadata[list(sim_metadata.keys())[i]]) for i in descending_indexes
    )

    return sim_metadata
