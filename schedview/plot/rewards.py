import warnings

import holoviews as hv
import numpy as np
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_sim.scheduler.model_observatory import ModelObservatory  # noqa F401

import schedview.collect.opsim
import schedview.collect.scheduler_pickle
import schedview.compute.astro
import schedview.compute.scheduler


def plot_survey_rewards(rewards):
    """Plot survey rewards as a function of time.

    Parameters
    ----------
    rewards : `pandas.DataFrame`
        Data with at least these columns:

        ``"survey_name"``
            The name of the survey (`str`).
        ``"time"``
            The sample time for the reward (`datetime64[ns]`).
        ``"reward"``
            The reward (`float`).

    Returns
    -------
    reward_plot : `bokeh.plotting.figure`
        The figure.
    """
    reward_plot = (
        rewards.replace([np.inf, -np.inf], np.nan)
        .loc[:, ["survey_name", "time", "reward"]]
        .hvplot(by=["survey_name"], x="time", y=["reward"], title="Rewards for each survey")
        .options({"Curve": {"color": hv.Cycle("Category20")}})
    )
    return reward_plot


def create_survey_reward_plot(
    scheduler,
    night_date,
    additional_visits=None,
    observatory=None,
    timezone="Chile/Continental",
):
    """Build a plot of rewards by survey for a time period.

    Parameters
    ----------
    scheduler : `rubin_sim.scheduler.schedulers.Core_scheduler` or `str`
        The scheduler with the surveys to evaluate, or the name of a file
        from which such a scheduler should be loaded.
    night_date : `astropy.time.Time`
        A time during the night to plot.
    additional_visits : `pandas.DataFrame` or `str`, optional
        Visits to add to the scheduler before reward evaluation,
        by default None
    observatory : `ModelObservatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None
    timezone : `str`, optional
        Timezone for horizontal axis, by default "Chile/Continental"

    Returns
    -------
    figure : `bokeh.plotting.figure`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_survey_rewards`.
    """

    site = None if observatory is None else observatory.location

    # Collect
    if isinstance(scheduler, str):
        scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(scheduler)
        scheduler.update_conditions(conditions)

    if isinstance(additional_visits, str):
        night_events = schedview.compute.astro.night_events(
            night_date=night_date, site=site, timezone=timezone
        )
        start_time = Time(night_events.loc["sunset", "UTC"])
        end_time = Time(night_events.loc["sunrise", "UTC"])
        additional_visits = schedview.collect.opsim.read_opsim(
            additional_visits, Time(start_time).iso, Time(end_time).iso
        )

    # Compute
    if additional_visits is not None:
        schedview.compute.scheduler.replay_visits(scheduler, additional_visits)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        rewards = schedview.compute.scheduler.compute_basis_function_rewards(scheduler)

    # Plot
    data = {"rewards": rewards}
    reward_plot = hv.render(plot_survey_rewards(**data))
    return reward_plot, data
