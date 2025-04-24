from urllib.parse import urljoin, urlparse

import numpy as np
import pandas as pd
import rubin_sim.maf
from rubin_scheduler.scheduler.utils import ObservationArray
from rubin_scheduler.utils.consdb import load_consdb_visits

import schedview.clientsite


def read_consdb(
    instrument: str = "lsstcam",
    *args,
    stackers: list[rubin_sim.maf.stackers.base_stacker.BaseStacker] = [],
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

    consdb_visits = load_consdb_visits(instrument, *args, url=url, **kwargs)
    # If the return is empty, to_records won't be able to determine the
    # right dtypes, so use ObservationArray()[0:0] instead to make the
    # empty recarray with the correct dtypes.
    visit_records: np.recarray = (
        consdb_visits.merged_opsim_consdb.to_records()
        if len(consdb_visits.opsim) > 0
        else ObservationArray()[0:0]
    )
    for stacker in stackers:
        visit_records = stacker.run(visit_records)
    visits = pd.DataFrame(visit_records)
    return visits
