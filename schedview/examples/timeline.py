import argparse
import asyncio
from typing import Literal

import astropy.utils.iers
import bokeh.embed
import bokeh.io
import bokeh.models

from schedview import DayObs
from schedview.collect import SAL_INDEX_GUESSES
from schedview.collect.timeline import collect_timeline_data
from schedview.compute.astro import get_median_model_sky, night_events
from schedview.compute.obsblocks import compute_block_spans
from schedview.plot.timeline import make_timeline_scatterplots


def make_timeline(
    iso_date: str,
    visit_source: str,
    telescope: Literal["AuxTel", "Simonyi"] = "Simonyi",
    report: None | str = None,
) -> bokeh.models.UIElement:
    """Make a timeline plot.

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    visit_source : `str`
        Instrument or baseline version number.
    telescope : `str`, optional
        The telescope to use, "AuxTel" or "Simonyi", by default "Simonyi".
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result: `bokeh.models.UIElement`
        Timeline plot.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)
    sal_indexes = tuple(SAL_INDEX_GUESSES[visit_source])

    # Collect
    data = asyncio.run(
        collect_timeline_data(
            day_obs,
            sal_indexes=sal_indexes,
            telescope=telescope,
            visit_origin=visit_source,
            visits=True,
            log_messages=True,
            scheduler_dependencies=True,
            scheduler_configuration=True,
            block_status=True,
            scheduler_snapshots=True,
        )
    )

    # Compute
    data["block_spans"] = compute_block_spans(data["block_status"])
    data["median_model_sky"] = get_median_model_sky(day_obs)
    data["sun"] = night_events(day_obs.date)

    # Plot
    result: bokeh.models.UIElement = make_timeline_scatterplots(**data)

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="timeline", description="Plot the timeline for a night.")
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument(
        "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
    )
    parser.add_argument("telescope", type=str, help="'AuxTel' or 'Simonyi'")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    make_timeline(args.date, args.visit_source, args.telescope, args.report)
