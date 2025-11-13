import argparse

from astropy.time import Time

import schedview.collect.efd


def scheduler_config_at_time_cli():

    # Get "now" so we can make it the default.
    now = Time.now()
    now_isot = now.isot
    assert isinstance(now.isot, str)

    # Prepare argument parsing
    parser = argparse.ArgumentParser(
        prog="scheduler_config_at_time",
        description="Get the scheduler configuration git ref and "
        "script path the observatory as of a given time.",
    )
    parser.add_argument(
        "what_scheduled", type=str, help="Which scheduler config (simonyi, maintel, ocs, or auxtel)."
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

    config_ref, config_file = schedview.collect.efd.get_scheduler_config(args.what_scheduled, time_cut)

    print(config_ref, config_file)


if __name__ == "__main__":
    scheduler_config_at_time_cli()
