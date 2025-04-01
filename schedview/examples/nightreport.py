import argparse
import datetime
from typing import Literal

import schedview.collect.nightreport
import schedview.compute.nightreport
import schedview.plot.nightreport
from schedview.dayobs import DayObs


def make_nightreport(
    iso_date: str | datetime.date,
    telescope: Literal["AuxTel", "Simonyi"] = "Simonyi",
    report: None | str = None,
) -> str:
    """Create a text night report.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    telescope : `str`
        Telescope for which to make a night report: "Simonyi" or "AuxTel".
        Defaults to "Simoniy".
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    report: `str`
        The night report, in markdown.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    night_reports: list[dict] = schedview.collect.nightreport.get_night_report(day_obs, telescope)
    """A list of different versions of the night report for the night."""

    # Compute
    # Try to guess the best one
    best_version_of_night_report: dict = schedview.compute.nightreport.best_night_report(night_reports)

    # Plot
    result: str = schedview.plot.nightreport.night_report_markdown(best_version_of_night_report)
    """The night report in markdown."""

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="nightreport", description="Print the night report as markdown.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("--telescope", type=str, default="Simonyi", help="Telescope, Simonyi or AuxTel")
    parser.add_argument("--report", type=str, default=None, help="output file name")
    args = parser.parse_args()

    result = make_nightreport(args.date, args.telescope, args.report)

    if args.report is None:
        print(result)
