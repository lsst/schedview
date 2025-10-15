import argparse
import datetime

import pandas as pd
from rubin_sim.sim_archive.prenightindex import get_prenight_index

from schedview.dayobs import DayObs

TELESCOPES = ("simonyi", "auxtel")

SIM_TABLE_COLUMNS = [
    "visitseq_uuid",
    "sim_creation_day_obs",
    "daily_id",
    "telescope",
    "scheduler_version",
    "config_url",
    "visitseq_url",
    "tags",
]


def get_prenight_table(
    day_obs: DayObs,
) -> str:
    """Create a data frame of pre-night simulations for a day obs.

    Parameters
    ----------
    day_obs : `schedview.DayObs`
        The date for which to get pre-night simulations.

    Returns
    -------
    result : `str`
        The table of prenight simulations.
    """

    # Collect
    raw_sim_metadata = [get_prenight_index(day_obs.date, telescope=t) for t in TELESCOPES]

    # Compute
    sim_metadata = pd.concat(raw_sim_metadata)
    if len(sim_metadata) < 1:
        return ""

    sim_metadata.sort_values(by="creation_time", ascending=True, inplace=True)
    prenight_df = sim_metadata.reset_index().loc[:, SIM_TABLE_COLUMNS]

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
