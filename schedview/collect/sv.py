import argparse
import datetime

import astropy
import pandas as pd
from rubin_scheduler.scheduler.utils import SchemaConverter
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


def get_sv_visits_cli(cli_args: list = []) -> None:
    parser = argparse.ArgumentParser(description="Create an opsim file with SV visits form a consdb query")
    parser.add_argument("opsim", type=str, help="Opsim file name")
    parser.add_argument(
        "--dayobs",
        type=str,
        default=DayObs.from_date(datetime.date.today().isoformat()),
        help="The day_obs of the night to simulate.",
    )
    args = parser.parse_args() if len(cli_args) == 0 else parser.parse_args(cli_args)

    day_obs = DayObs.from_date(args.dayobs)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    sv_visits = read_visits(day_obs)
    if "scheduler_note" in sv_visits.columns:
        sv_visits["note"] = sv_visits["scheduler_note"]

    # Be sure to apply any conversions in Schema Converter by converting
    # the df we have (which has extra columns) to an obs array,
    # then write it to disk as an opsim with the SchemaConverter.
    schema_converter = SchemaConverter()
    obs = schema_converter.opsimdf2obs(sv_visits)
    schema_converter.obs2opsim(obs, args.opsim)
