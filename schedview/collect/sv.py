import pandas as pd
from rubin_sim import maf

import schedview.collect.visits
from schedview import DayObs

CONSDB_CONSTRAINTS = """v.day_obs >= 20250620
    AND v.science_program = 'BLOCK-365'
    AND v.observation_reason NOT LIKE 'block-t548'
    AND v.observation_reason != 'field_survey_science'
"""
CONSDB_NUM_NIGHTS = 36500
INSTRUMENT = "lsstcam"


def read_visits(
    day_obs: str | int | DayObs,
    stackers: list[maf.stackers.base_stacker.BaseStacker] = schedview.collect.visits.NIGHT_STACKERS,
) -> pd.DataFrame:
    """Read visits from a variety of possible sources.

    Parameters
    ----------
    day_obs : `str` or `int` or `DayObs`
        The night of observing as a dayobs.
    stackers : `list` of `maf.stackers.base_stacker.BaseStacker` subclasses
        The stackers to apply.

    Returns
    -------
    visits : `pd.DataFrame`
        A `pd.DataFrame` of visits.

    """
    visits = schedview.collect.visits.read_visits(
        day_obs,
        INSTRUMENT,
        stackers=stackers,
        num_nights=CONSDB_NUM_NIGHTS,
        constraints=CONSDB_CONSTRAINTS,
    )
    return visits
