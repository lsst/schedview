import argparse
import asyncio
from typing import Literal

import astropy.utils.iers
import bokeh.io
from bokeh.models.ui.ui_element import UIElement

from schedview import DayObs
from schedview.collect.efd import SAL_INDEX_GUESSES
from schedview.collect.timeline import collect_timeline_data
from schedview.compute.astro import get_median_model_sky, night_events
from schedview.compute.obsblocks import compute_block_spans
from schedview.plot.timeline import make_timeline_scatterplots


async def run_full_timeline_pipeline(
    evening_date: str,
    telescope: Literal["AuxTel", "Simonyi"] = "Simonyi",
    visit_origin: str = "lsstcomcam",
) -> UIElement:
    """Make a timeline plot, begin to end.

    Parameters
    ----------
    evening_date : `str`
        The evening of the night for which to make the timeline YYYY-MM-DD.
    telescope : `str`, optional
        The telescope to use, "AuxTel" or "Simonyi". By default "Simonyi"
    visit_origin : `str`, optional
        The source for visit data, by default "lsstcomcam"

    Returns
    -------
    plot: `UIElement`
        A bokeh UI element that can be show or saved.
    """

    day_obs: DayObs = DayObs.from_date(evening_date)
    sal_indexes = tuple(SAL_INDEX_GUESSES[visit_origin])

    data = await collect_timeline_data(
        day_obs,
        sal_indexes=sal_indexes,
        telescope=telescope,
        visit_origin=visit_origin,
        visits=True,
        log_messages=True,
        scheduler_dependencies=True,
        scheduler_configuration=True,
        block_status=True,
        scheduler_snapshots=True,
    )

    data["block_spans"] = compute_block_spans(data["block_status"])
    data["median_model_sky"] = get_median_model_sky(day_obs)
    data["sun"] = night_events(day_obs.date)

    plot = make_timeline_scatterplots(**data)

    return plot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="timeline", description="Plot the timeline for a night.")
    parser.add_argument("filename", type=str, help="output file name")
    parser.add_argument("evening_date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("--telescope", type=str, default="Simonyi", help="'AuxTel' or 'Simonyi'")
    parser.add_argument(
        "--visit_origin",
        type=str,
        default="lsstcomcam",
        help="Where to get visits from",
    )
    args = parser.parse_args()

    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

    plot = asyncio.run(run_full_timeline_pipeline(args.evening_date, args.telescope, args.visit_origin))
    bokeh.io.save(plot, args.filename)
