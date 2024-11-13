import numpy as np
import pandas as pd
import rubin_sim.maf
from rubin_scheduler.scheduler.utils import ObservationArray
from rubin_scheduler.utils.consdb import load_consdb_visits


def read_consdb(
    instrument: str = "lsstcomcamsim",
    *args,
    stackers: list[rubin_sim.maf.stackers.base_stacker.BaseStacker] = [],
    **kwargs,
) -> pd.DataFrame:
    consdb_visits = load_consdb_visits(instrument, *args, **kwargs)
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
