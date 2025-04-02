import argparse
import asyncio

from astropy.time import Time

import schedview.collect

GITHUB_API_URL_BASE = "https://api.github.com/repos"


def scheduler_config_at_time_cli():

    # Get "now" so we can make it the default.
    now = Time.now()
    now_isot = now.isot
    assert isinstance(now.isot, str)

    # Prepare argument parsing
    parser = argparse.ArgumentParser(
        prog="scheduler_config_at_time",
        description="Get the scheduler configuration script path the observatory as of a given time.",
    )
    parser.add_argument(
        "instrument", type=str, help="The instrument being scheduled (lsstcam, latiss, or lsstcomcam)."
    )
    parser.add_argument(
        "--datetime",
        type=str,
        default=f"{now_isot[:19]}Z",
        help="UTC time in ISO 8601 T format: YYYY-MM-DDTHH:mm:SSZ",
    )

    # Actually parse the arguments.
    args = parser.parse_args()

    # Do the call
    time_cut = Time(args.datetime)
    ts_config_ocs_version = schedview.collect.get_version_at_time("ts_config_ocs", time_cut)

    sal_indexes = schedview.collect.SAL_INDEX_GUESSES[args.instrument]
    loop = asyncio.get_event_loop()
    scheduler_config = loop.run_until_complete(
        schedview.collect.get_scheduler_config(ts_config_ocs_version, sal_indexes, time_cut)
    )

    print(scheduler_config)


if __name__ == "__main__":
    scheduler_config_at_time_cli()
