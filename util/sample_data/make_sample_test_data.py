import argparse
import lzma
import pickle
import warnings

import numpy as np
from astropy.time import Time
from rubin_sim.scheduler import sim_runner
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.scheduler.utils import SchemaConverter
from rubin_sim.utils import survey_start_mjd

DEFAULT_DATE = Time(survey_start_mjd(), format="mjd").iso[:10]

# Several dependencies throw prodigious instances of (benign) warnings.
# Suppress them to avoid poluting the executed notebook.

warnings.filterwarnings(
    "ignore",
    module="astropy.time",
    message="Numerical value without unit or explicit format passed to TimeDelta, assuming days",
)
warnings.filterwarnings(
    "ignore",
    module="healpy",
    message="divide by zero encountered in divide",
)
warnings.filterwarnings(
    "ignore",
    module="healpy",
    message="invalid value encountered in multiply",
)
warnings.filterwarnings(
    "ignore",
    module="holoviews",
    message="Discarding nonzero nanoseconds in conversion.",
)
warnings.filterwarnings(
    "ignore",
    module="rubin_sim",
    message="invalid value encountered in arcsin",
)
warnings.filterwarnings(
    "ignore",
    module="rubin_sim",
    message="All-NaN slice encountered",
)


def make_sample_test_data():
    parser = argparse.ArgumentParser(description="Generate sample test data for testing schedview.")
    parser.add_argument(
        "--opsim_output_fname",
        type=str,
        default="sample_opsim.db",
        help="Filename for the opsim output.",
    )
    parser.add_argument(
        "--scheduler_fname",
        type=str,
        default="sample_scheduler.pickle.xz",
        help="Filename for the scheduler pickle file.",
    )
    parser.add_argument(
        "--rewards_fname",
        type=str,
        default="sample_rewards.h5",
        help="Filename for the rewards file.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=DEFAULT_DATE,
        help="Date of the night to simulate (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    opsim_output_fname = args.opsim_output_fname
    scheduler_fname = args.scheduler_fname
    rewards_fname = args.rewards_fname
    evening_iso8601 = args.date

    # Set the start date, scheduler, and observatory for the night:

    observatory = ModelObservatory()

    # Set `evening_mjd` to the integer calendar MJD of the local calendar day
    # on which sunset falls on the night of interest.
    evening_mjd = Time(evening_iso8601).mjd

    # If we just use this day as the start and make the simulation duration 1
    # day, the begin and end of the simulation will probably begin in the
    # middle on one night and end in the middle of the next.
    # Instead, find the sunset and sunrise of the night we want using the
    # almanac, and use these to determine our start time and duration.

    # If the date represents the local calendar date at sunset, we need to
    # shift by the longitude in units of days
    this_night = (
        np.floor(observatory.almanac.sunsets["sunset"] + observatory.site.longitude / 360) == evening_mjd
    )

    mjd_start = observatory.almanac.sunsets[this_night]["sun_n12_setting"][0]
    mjd_end = observatory.almanac.sunsets[this_night]["sunrise"][0]

    night_duration = mjd_end - mjd_start

    observatory = ModelObservatory(mjd_start=mjd_start)

    scheduler = example_scheduler(mjd_start=mjd_start)
    scheduler.keep_rewards = True

    observatory, scheduler, observations, reward_df, obs_rewards = sim_runner(
        observatory,
        scheduler,
        mjd_start=mjd_start,
        survey_length=night_duration,
        record_rewards=True,
    )

    SchemaConverter().obs2opsim(observations, filename=opsim_output_fname)

    with lzma.open(scheduler_fname, "wb", format=lzma.FORMAT_XZ) as pio:
        sched_cond_tuple = (scheduler, scheduler.conditions)
        pickle.dump(sched_cond_tuple, pio)

    reward_df.to_hdf(rewards_fname, "reward_df")
    obs_rewards.to_hdf(rewards_fname, "obs_rewards")


if __name__ == "__main__":
    make_sample_test_data()
