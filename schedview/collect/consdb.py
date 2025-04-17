import warnings

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import ObservationArray
from rubin_scheduler.utils.consdb import load_consdb_visits
from rubin_sim.maf.stackers.base_stacker import BaseStacker
from rubin_sim.maf.stackers.date_stackers import ObservationStartTimestampStacker


def read_consdb(
    instrument: str = "lsstcam",
    *args,
    stackers: list[BaseStacker] = [ObservationStartTimestampStacker()],
    **kwargs,
) -> pd.DataFrame:

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
        visit_records: np.recarray = consdb_visits.merged_opsim_consdb.to_records()
    else:
        # If the array is empty, pass back an empty array with the correct
        # columns and types.
        visit_records = ObservationArray()[0:0]

    for stacker in stackers:
        visit_records = stacker.run(visit_records)

    visits = pd.DataFrame(visit_records)

    return visits
