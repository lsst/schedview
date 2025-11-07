import argparse
import datetime

import pandas as pd
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview.compute.visits
import schedview.plot
from schedview.dayobs import DayObs


def make_sunmoon(
    iso_date: str | datetime.date,
    report: None | str = None,
) -> str:
    """Make sun and moon tables.

    Parameters
    ----------
    iso_date : `str` or `datetime.date`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    resurt: `str`
        The tables in markdown.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect

    # Compute
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)
    mjd = night_events.loc["night_middle", "MJD"]

    observatory: ModelObservatory = ModelObservatory(no_sky=True, mjd=mjd)
    positions: pd.DataFrame = schedview.compute.astro.compute_sun_moon_positions(observatory)

    # Plot
    result: str = f"""## Sun and moon

### Events

{night_events.to_markdown()}

Modified Julian Date (MJD) is in units of days (UTC). Local Sidereal Time (LST) is in units of degrees.

### Positions at local solar midnight

{positions.to_markdown()}
"""

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(result, file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="sunmoon", description="Make a table of sun and moon events and positions."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    make_sunmoon(args.date, args.report)
