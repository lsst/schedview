import argparse
from typing import Literal

import astropy.utils.iers

import schedview.plot.nightreport
from schedview import DayObs
from schedview.collect import get_night_report
from schedview.compute.nightreport import best_night_report


def format_night_report(
    night: str,
    telescope: Literal["AuxTel", "Simonyi"],
    user_params: dict | None = None,
) -> str:
    day_obs: DayObs = DayObs.from_date(night)

    # Query consdb for all night reports for the night
    night_reports: list[dict] = get_night_report(day_obs, telescope, user_params)

    # Try to guess the best one
    best_version_of_night_report: dict = best_night_report(night_reports)

    # Format it in markdown
    night_report_markdown: str = schedview.plot.nightreport.night_report_markdown(
        best_version_of_night_report
    )
    return night_report_markdown


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="nightreport", description="Print the night report as markdown.")
    parser.add_argument("night", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("--telescope", type=str, default="Simonyi", help="Evening YYYY-MM-DD")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    night_report_md: str = format_night_report(args.night, args.telescope)
    print(night_report_md)
