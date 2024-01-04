from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import yaml
from astropy.time import Time
from lsst.resources import ResourcePath


def read_rewards(rewards_uri, start_time="2000-01-01", end_time="2100-01-01"):
    """Read rewards from an rewards table recorded by the scheduler.

    Parameters
    ----------
    opsim_uri : `str`
        The uri from which to rewards.
    start_time : `str`, `astropy.time.Time`
        The start time for rewards to be loaded.
    end_time : `str`, `astropy.time.Time`
        The end time for rewards ot be loaded.

    Returns
    -------
    rewards_df, obs_rewards : `tuple` [`pandas.DataFrame`]
        The rewards and obs rewards data frames.
    """
    start_mjd = Time(start_time).mjd
    end_mjd = Time(end_time).mjd

    # Make sure we use a time window which includes the start and end times.
    start_mjd = np.nextafter(start_mjd, start_mjd - 1)
    end_mjd = np.nextafter(end_mjd, end_mjd + 1)

    original_resource_path = ResourcePath(rewards_uri)

    if original_resource_path.isdir():
        # If we were given a directory, look for a metadata file in the
        # directory, and look up in it what file to load observations from.
        metadata_path = original_resource_path.join("sim_metadata.yaml")
        sim_metadata = yaml.safe_load(metadata_path.read().decode("utf-8"))
        try:
            rewards_basename = sim_metadata["files"]["rewards"]["name"]
        except KeyError:
            rewards_df = None
            obs_rewards = None
            return rewards_df, obs_rewards

        rewards_path = original_resource_path.join(rewards_basename)
    else:
        # otherwise, assume we were given the path to the observations file.
        rewards_path = original_resource_path

    # ResourcePath.as_local runs into threading problems when used with
    # bokeh/panel, so write the file to a temporary directory and read it
    # "by hand" here.
    rewards_bytes = rewards_path.read()

    with TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir).joinpath("rewards.h5")
        with open(temp_file, "wb") as rewards_io:
            rewards_io.write(rewards_bytes)

        try:
            rewards_df = pd.read_hdf(temp_file, key="reward_df")
            rewards_df.query(f"{start_mjd} <= queue_start_mjd <= {end_mjd}", inplace=True)
        except KeyError:
            rewards_df = None

        try:
            obs_rewards = pd.read_hdf(temp_file, key="obs_rewards")
            obs_rewards = obs_rewards.loc[start_mjd:end_mjd]
        except KeyError:
            obs_rewards = None

    return rewards_df, obs_rewards
