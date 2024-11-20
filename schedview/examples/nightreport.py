from typing import Literal

import schedview.collect.nightreport
import schedview.compute.nightreport
import schedview.plot.nightreport
from schedview import DayObs


def night_report(
    day_obs: DayObs,
    telescope: Literal["AuxTel", "Simonyi"],
    api_endpoint: str = "https://usdf-rsp-dev.slac.stanford.edu/nightreport/reports",
    user_params: dict | None = None,
) -> str:
    # Query consdb for all night reports for the night
    night_reports: list[dict] = schedview.collect.nightreport.get_night_report(
        day_obs, telescope, api_endpoint, user_params
    )

    # Try to guess the best one
    best_version_of_night_report: dict = schedview.compute.nightreport.best_night_report(night_reports)

    # Format it in markdown
    night_report_markdown: str = schedview.plot.nightreport.night_report_markdown(
        best_version_of_night_report
    )
    return night_report_markdown
