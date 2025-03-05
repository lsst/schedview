import argparse
import datetime

from astropy.time import Time

import schedview.collect


def versions_at_time(
    iso_time: str | datetime.datetime,
    report: None | str = None,
) -> str:
    """Create a table of versions of products used at a given time.

    Parameters
    ----------
    iso_time : `str` or `datetime.datetime`
        Local calendar date and time for which versions are to be retrieved,
        in YYYY-MM-DDTHH:mm:SSZ (ISO 8601) format.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    report: `str`
        The narrative log text.
    """

    # Parameters
    time_cut = Time(iso_time)

    # Collect
    versions = schedview.collect.make_version_table_for_time(time_cut)

    # Compute

    # Plot
    result: str = versions.to_markdown()

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="versionsattime", description="Make a narrative log for a night in markdown."
    )
    parser.add_argument("datetime", type=str, help="UTC time in ISO 8601 T format: YYYY-MM-DDTHH:mm:SSZ")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    versions_at_time(args.datetime, args.report)
