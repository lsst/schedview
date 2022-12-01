import warnings

import hvplot.pandas
import holoviews as hv
import numpy as np
from astropy.time import Time

import schedview.collect.scheduler_pickle
import schedview.collect.opsim
import schedview.compute.scheduler
import schedview.compute.astro

def plot_survey_rewards(rewards):
    reward_plot = (
        rewards
        .replace([np.inf, -np.inf], np.nan)
        .hvplot(by=["survey_name"], x="time", y=["reward"], title="Rewards for each survey")
        .options({"Curve": {"color": hv.Cycle("Category20")}})
    )
    return reward_plot    

def create_survey_reward_plot(scheduler, night_date, additional_visits=None, observatory=None, timezone="Chile/Continental"):
    """Build a plot of rewards by survey for a time period
    """

    site = None if observatory is None else observatory.location
    
    # Collect
    if isinstance(scheduler, str):
        scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(scheduler)
        scheduler.update_conditions(conditions)

    if isinstance(additional_visits, str):
        night_events = schedview.compute.astro.night_events(night_date=night_date, site=site, timezone=timezone)
        start_time = Time(night_events.loc["sunset", "UTC"])
        end_time = Time(night_events.loc["sunrise", "UTC"])
        additional_visits = schedview.collect.opsim.read_opsim(additional_visits, Time(start_time).iso, Time(end_time).iso)
    
    # Compute
    if additional_visits is not None:
        schedview.compute.scheduler.replay_visits(scheduler, additional_visits)
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=FutureWarning)
        rewards = schedview.compute.scheduler.compute_basis_function_rewards(scheduler)
        
    # Plot
    data = {'rewards': rewards}
    reward_plot = hv.render(plot_survey_rewards(**data))
    return reward_plot, data

    