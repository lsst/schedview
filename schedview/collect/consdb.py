import warnings
from urllib.parse import urljoin, urlparse

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import ObservationArray
from rubin_scheduler.utils.consdb import load_consdb_visits
from rubin_sim.maf.stackers.base_stacker import BaseStacker
from rubin_sim.maf.stackers.date_stackers import ObservationStartTimestampStacker

import schedview.clientsite


def read_consdb(
    instrument: str = "lsstcam",
    *args,
    stackers: list[BaseStacker] = [ObservationStartTimestampStacker()],
    url: str = "consdb/query",
    **kwargs,
) -> pd.DataFrame:
    """Query the consdb for visits.

    Parameters
    ----------
    instrument : `str`
        The instrument for which to get visits (lsstcam or latiss)
    stackers : `list`
        A list of MAF stackers to use to add columns. An empyt list by
        default.
    url: `str`
        The endpoint URL for the consdb to use. By default, infer from
        schedview.clientsite.DATASOURCE_BASE_URL.
    Returns
    -------
    visits : `pandas.DataFrame`
        The visits retrieved from the consdb.
    """

    # If we are only passed a relative URL, turn it into an absolute one
    # using client site parameters.
    if urlparse(url).netloc == "":
        url = urljoin(schedview.clientsite.DATASOURCE_BASE_URL, url)

    found_timestamp_stacker = False
    for stacker in stackers:
        found_timestamp_stacker = found_timestamp_stacker or isinstance(
            stacker, ObservationStartTimestampStacker
        )
    if not found_timestamp_stacker:
        warnings.warn(
            "read_consdb called without an ObservationStartTimestampStacker. "
            "This may break plots that rely on the time."
        )

    consdb_visits = load_consdb_visits(instrument, *args, **kwargs)

    if len(consdb_visits.consdb_visits) > 0:
        # Make sure the visits are in order so the overhead stacker works.
        # Filter out visits with a None visit_id: it breaks the sorting,
        # and if visit_id is None, it means something went very wrong
        # with that visit anyway.
        visit_records: np.recarray = (
            consdb_visits.merged_opsim_consdb.query("visit_id.notnull()").sort_values("visit_id").to_records()
        )
    else:
        # If the array is empty, pass back an empty array with the correct
        # columns and types.
        visit_records = ObservationArray()[0:0]

    if len(visit_records) > 0:
        for stacker in stackers:
            visit_records = stacker.run(visit_records)

    visits = pd.DataFrame(visit_records)

    return visits
