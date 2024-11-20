import pandas as pd

import schedview.collect.visits
import schedview.compute.astro
import schedview.compute.visits
import schedview.plot
from schedview import DayObs


def overhead_table(
    visit_source: str = "3.5",
    day_obs: DayObs = DayObs.from_date("2026-03-15"),
) -> str:
    # Get the time for which to get positions: the middle of the night
    # of the provided DayObs.
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)

    # Get the visits
    visits: pd.DataFrame = schedview.collect.visits.read_visits(
        day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
    )

    overhead_summary = schedview.compute.visits.compute_overhead_summary(
        visits,
        night_events.loc["sun_n12_setting", "MJD"],
        night_events.loc["sun_n12_rising", "MJD"],
    )
    summary_table = schedview.plot.create_overhead_summary_table(overhead_summary)
    return summary_table
