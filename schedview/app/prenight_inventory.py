import argparse
import datetime
import os

import pandas as pd
from rubin_sim.sim_archive import read_archived_sim_metadata

from schedview.compute import munge_sim_archive_metadata
from schedview.dayobs import DayObs

SIM_TABLE_COLUMNS = (
    "resource_url",
    "sim_execution_date",
    "sim_index",
    "telescope",
    "scheduler_version",
    "opsim_config_version",
    "opsim_config_script",
    "tags",
)


def get_prenight_table(
    day_obs: DayObs,
    archive_uri="s3://rubin:rubin-scheduler-prenight/opsim/",
    num_nights=7,
) -> str:
    """Create a data frame of pre-night simulations for a day obs.

    Parameters
    ----------
    day_obs : `schedview.DayObs`
        The date for which to get pre-night simulations.
    archive_uri : `str`
        The URL for the archive in which to look for simulations.
    num_nights : `int`
        Then number of nights before the requested night for which to look
        for simulatiotns.

    Returns
    -------
    result : `pandas.DataFrame`
        The table of prenight simulations.
    """

    # Make sure conditions are met.
    if archive_uri.startswith("s3://rubin:rubin-scheduler-prenight"):
        # If the archive is the standard USDF one, fail with an informative
        # error if the environment is not set up to do that.
        # Otherwise, it will fail with an uninformative error.
        if os.environ["LSST_DISABLE_BUCKET_VALIDATION"] != "1":
            raise RuntimeError("Environment variable LSST_DISABLE_BUCKET_VALIDATION must be set to 1")

    if archive_uri.startswith("s3:"):
        if "S3_ENDPOINT_URL" not in os.environ:
            raise RuntimeError(
                "Environment variable  S3_ENDPOINT_URL must be set, "
                + "perhaps to https://s3dfrgw.slac.stanford.edu/ ."
            )

    # Collect
    raw_sim_metadata = read_archived_sim_metadata(
        archive_uri, num_nights=num_nights, compilation_resource=f"{archive_uri}compiled_metadata_cache.h5"
    )

    # Compute
    sim_metadata = munge_sim_archive_metadata(raw_sim_metadata, day_obs, archive_uri)
    prenight_df = pd.DataFrame(sim_metadata).T
    prenight_df.index.name = "resource_url"
    prenight_df = prenight_df.reset_index().loc[:, SIM_TABLE_COLUMNS]

    # "Plot"
    prenight_table = "#" + prenight_df.to_csv(sep="\t", index=False)

    return prenight_table


def prenight_inventory_cli():
    parser = argparse.ArgumentParser(
        prog="list_prenights", description="Print a table of prenight simulations for a night."
    )
    parser.add_argument("date", type=str, nargs="?", default="today", help="Evening YYYY-MM-DD")
    args = parser.parse_args()

    if args.date == "today":
        day_obs = DayObs.from_date(datetime.date.today())
    else:
        day_obs = DayObs.from_date(args.date)

    prenight_table = get_prenight_table(day_obs)
    print(prenight_table)


if __name__ == "__main__":
    prenight_inventory_cli()
