import argparse

import bokeh.embed
import bokeh.io
import bokeh.models
import lsst.resources
import numpy as np
import pandas as pd

import schedview.collect.rewards
import schedview.plot
from schedview.dayobs import DayObs


def make_survey_reward_plot(
    iso_date: str,
    reward_source: str,
    report: None | str = None,
) -> bokeh.models.UIElement:
    """Make a visualization showing rewards by survey.

    Parameters
    ----------
    iso_date : `str`
        Local calendar date of the evening on which the night starts,
        in YYYY-MM-DD (ISO 8601) format.
    reward_source : `str`
        The URI of the hdf5 file with the rewards.
    report : `None` | `str`, optional
        Report file name, by default ``None`` (to not write to a file).

    Returns
    -------
    result: `bokeh.models.UIElement`
        The visualization of the rewards by survey.
    """

    # Parameters
    day_obs: DayObs = DayObs.from_date(iso_date)

    # Collect
    rewards_rp: lsst.resources.ResourcePath = lsst.resources.ResourcePath(reward_source)
    maybe_rewards_df = schedview.collect.rewards.read_rewards(rewards_rp)[0]
    assert isinstance(maybe_rewards_df, pd.DataFrame)
    rewards_df: pd.DataFrame = maybe_rewards_df

    # Compute
    # A work-around for bokeh's inability to handle numpy.int64
    rewards_df["queue_fill_mjd_ns"] = rewards_df["queue_fill_mjd_ns"].astype(np.float64)

    # Plot
    maybe_result = schedview.plot.rewards.reward_timeline_for_surveys(rewards_df, day_obs.mjd)
    assert isinstance(maybe_result, bokeh.models.UIElement)
    result: bokeh.models.UIElement = maybe_result

    # Report
    if report is not None:
        with open(report, "w") as report_io:
            print(bokeh.embed.file_html(result), file=report_io)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="surveyrewards", description="Create a visualization showing rewards by survey."
    )
    parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
    parser.add_argument("rewards_source", type=str, help="URI of the hdf5 file with the rewards.")
    parser.add_argument("report", type=str, help="output file name")
    args = parser.parse_args()

    make_survey_reward_plot(args.date, args.rewards_source, args.report)
