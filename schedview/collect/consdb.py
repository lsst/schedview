import numpy as np
import pandas as pd
import rubin_sim.maf
from rubin_scheduler.utils.consdb import load_consdb_visits


def read_consdb(
    instrument: str = "lsstcomcamsim",
    *args,
    stackers: list[rubin_sim.maf.stackers.base_stacker.BaseStacker] = [],
    **kwargs,
) -> pd.DataFrame:
    consdb_visits = load_consdb_visits(instrument, *args, **kwargs)
    visit_records: np.recarray = consdb_visits.opsim.to_records()
    for stacker in stackers:
        visit_records = stacker.run(visit_records)
    visits = pd.DataFrame(visit_records)
    return visits
