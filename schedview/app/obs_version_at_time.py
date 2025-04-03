import argparse
import re

import requests
from astropy.time import Time

import schedview.collect

GITHUB_API_URL_BASE = "https://api.github.com/repos"


def version_at_time_cli():

    # Get "now" so we can make it the default.
    now = Time.now()
    now_isot = now.isot
    assert isinstance(now.isot, str)

    # Prepare argument parsing
    parser = argparse.ArgumentParser(
        prog="summit_version_at_time",
        description="Get the version of something at the observatory as of a given time.",
    )
    parser.add_argument("item", type=str, help="The thing to get the version of.")
    parser.add_argument(
        "--datetime",
        type=str,
        default=f"{now_isot[:19]}Z",
        help="UTC time in ISO 8601 T format: YYYY-MM-DDTHH:mm:SSZ",
    )
    parser.add_argument("--hash", action="store_true", help="Return the full git hash.")
    parser.add_argument("--user", type=str, default="lsst-ts", help="Return the full git hash.")

    # Actually parse the arguments.
    args = parser.parse_args()

    # Do the call
    time_cut = Time(args.datetime)
    version = schedview.collect.get_version_at_time(args.item, time_cut)

    # If we were asked for a hash rather than a version number,
    # ask github for it.
    if args.hash:
        git_url = "/".join([GITHUB_API_URL_BASE, args.user, args.item, "commits", version])
        response = requests.get(git_url).json()
        try:
            result = response["sha"]
        except KeyError:
            # Maybe the tag is prefixed by a "v"
            if re.match(r"^(\d+)\.(\d+)\.(\d+)$", version):
                git_url = "/".join([GITHUB_API_URL_BASE, args.user, args.item, "commits", "v" + version])
                response = requests.get(git_url).json()
                result = response["sha"]
            else:
                raise
    else:
        result = version

    print(result)


if __name__ == "__main__":
    version_at_time_cli()
