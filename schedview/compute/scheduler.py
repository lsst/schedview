import copy
import datetime
import inspect
import lzma
import numbers
import pickle

import numpy as np
import pandas as pd
from astropy.time import Time
from astropy.timeseries import TimeSeries
from rubin_scheduler.scheduler import sim_runner, surveys
from rubin_scheduler.scheduler.example import example_scheduler
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.scheduler.utils import SchemaConverter


def replay_visits(scheduler, visits):
    """Update a scheduler instances with a set of visits.

    Parameters
    ----------
    scheduler : `rubin_scheduler.scheduler.CoreScheduler`
        An instance of the scheduler to update
    visits : `pandas.DataFrame`
        A table of visits to add.
    """
    obs = SchemaConverter().opsimdf2obs(visits)
    for this_obs in obs:
        scheduler.add_observation(this_obs)

    scheduler.conditions.mjd = float(
        this_obs["mjd"] + (this_obs["slewtime"] + this_obs["visittime"]) / (24 * 60 * 60)
    )


def compute_basis_function_reward_at_time(scheduler, time, observatory=None):
    if observatory is None:
        observatory = ModelObservatory(nside=scheduler.nside)

    ap_time = Time(time)
    observatory.mjd = ap_time.mjd
    conditions = observatory.return_conditions()

    reward_df = scheduler.make_reward_df(conditions)
    summary_df = reward_df.reset_index()

    def make_tier_name(row):
        tier_name = f"tier {row.list_index}"
        return tier_name

    summary_df["tier"] = summary_df.apply(make_tier_name, axis=1)

    def get_survey_name(row):
        try:
            survey_name = scheduler.survey_lists[row.list_index][row.survey_index].survey_name
        except AttributeError:
            survey_name = ""

        if len(survey_name) == 0:
            class_name = scheduler.survey_lists[row.list_index][row.survey_index].__class__.__name__
            survey_name = f"{class_name}_{row.list_index}_{row.survey_index}"
        return survey_name

    summary_df["survey_name"] = summary_df.apply(get_survey_name, axis=1)

    def make_survey_row(survey_bfs):
        infeasible_bf = ", ".join(survey_bfs.loc[~survey_bfs.feasible.astype(bool)].basis_function.to_list())
        infeasible = ~np.all(survey_bfs.feasible.astype(bool))
        reward = survey_bfs.max_accum_reward.iloc[-1]

        survey_row = pd.Series(
            {
                "reward": reward,
                "infeasible": infeasible,
                "infeasible_bfs": infeasible_bf,
            }
        )
        return survey_row

    survey_df = summary_df.groupby(["tier", "survey_name"]).apply(make_survey_row)
    return survey_df


def compute_basis_function_rewards(scheduler, sample_times=None, observatory=None):
    if observatory is None:
        observatory = ModelObservatory(nside=scheduler.nside)

    if sample_times is None:
        # Compute values for the current night by default.
        sample_times = pd.date_range(
            Time(float(scheduler.conditions.sun_n12_setting), format="mjd", scale="utc").datetime,
            Time(float(scheduler.conditions.sun_n12_rising), format="mjd", scale="utc").datetime,
            freq="10T",
        )

    if isinstance(sample_times, TimeSeries):
        sample_times = sample_times.to_pandas()

    reward_list = []
    for time in sample_times:
        this_time_reward = compute_basis_function_reward_at_time(scheduler, time, observatory)
        this_time_reward["mjd"] = Time(time).mjd
        this_time_reward["time"] = time
        reward_list.append(this_time_reward)

    rewards = pd.concat(reward_list).reset_index()

    return rewards


def _normalize_time(this_time):
    if isinstance(this_time, Time):
        this_time = this_time
    if this_time is None:
        this_time = Time.now(scale="utc")
    elif isinstance(this_time, numbers.Number) and 51544 < this_time < 88069:
        this_time = Time(this_time, format="mjd", scale="utc")
    elif isinstance(this_time, str) or isinstance(this_time, datetime.datetime):
        this_time = Time(this_time, scale="utc")
    elif isinstance(this_time, pd.Timestamp):
        this_time = Time(this_time.to_pydatetime(), scale="utc")

    return this_time


def create_example(
    current_time=None,
    survey_start="2025-01-01T16:00:00Z",
    nside=None,
    simulate=True,
    scheduler_pickle_fname=None,
    opsim_db_fname=None,
    rewards_fname=None,
):
    """Create an example scheduler and observatory.

    Parameters
    ----------
    current_time : `float`, `str`, `datetime.datetime`, `pandas.Timestamp`,
        or `astropy.time.Time`
        The time to initialize the observatory and conditions to.
        Floats are interpreted as MJD. Strings are interpreted as UTC.
        If None, use the current time.
        Defaults no None.
    survey_start : `float`, `str`, `datetime.datetime`, `pandas.Timestamp`,
        or `astropy.time.Time`
        The survey start time.
    nside : `int`
        The nside to use for the scheduler and observatory. If None, use the
        default nside for the example scheduler.
    simulate : `bool`
        Run a sample simulation from survey_start to current_time
    scheduler_pickle_fname : `str`
        The filename to save the scheduler to.
    opsim_db_fname : `str`
        The filename to save the opsim database to.
    rewards_fname : `str`
        The filename to save the rewards to.

    Returns
    -------
    scheduler : `rubin_scheduler.scheduler.schedulers.CoreScheduler`
        The scheduler instance.
    observatory : `rubin_scheduler.models.ModelObservatory`
        The observatory instance.
    conditions : `rubin_scheduler.scheduler.features.Conditions`
        The conditions at the current time.
    observations : `pd.DataFrame`
        The observations from the simulation.
    """

    record_rewards = rewards_fname is not None

    current_time = _normalize_time(current_time)
    survey_start = _normalize_time(survey_start)

    if nside is None:
        scheduler = example_scheduler(mjd_start=survey_start.mjd)
        nside = scheduler.nside
    else:
        scheduler = example_scheduler(nside=nside, mjd_start=survey_start.mjd)

    observatory = ModelObservatory(nside=nside, mjd_start=survey_start.mjd)

    if simulate:
        sim_duration = current_time.mjd - survey_start.mjd
        if record_rewards:
            scheduler.keep_rewards = True
            observatory, scheduler, observations, reward_df, obs_rewards = sim_runner(
                observatory,
                scheduler,
                sim_start_mjd=survey_start.mjd,
                sim_duration=sim_duration,
                record_rewards=True,
            )
            reward_df.to_hdf(rewards_fname, "reward_df")
            obs_rewards.to_hdf(rewards_fname, "obs_rewards")
        else:
            observatory, scheduler, observations = sim_runner(
                observatory,
                scheduler,
                sim_start_mjd=survey_start.mjd,
                sim_duration=sim_duration,
            )

        if opsim_db_fname is not None:
            converter = SchemaConverter()
            converter.obs2opsim(observations, filename=opsim_db_fname, delete_past=True)
    else:
        observations = None

    observatory.mjd = current_time.mjd
    conditions = observatory.return_conditions()
    scheduler.update_conditions(conditions)

    if scheduler_pickle_fname is not None:
        if scheduler_pickle_fname.endswith(".xz"):
            with lzma.open(scheduler_pickle_fname, "wb", format=lzma.FORMAT_XZ) as out_file:
                pickle.dump((scheduler, scheduler.conditions), out_file)
        else:
            with open(scheduler_pickle_fname, "wb") as out_file:
                pickle.dump((scheduler, scheduler.conditions), out_file)

    result = (scheduler, observatory, conditions, observations)
    if record_rewards:
        result += (reward_df, obs_rewards)

    return result


def make_unique_survey_name(scheduler, survey_index=None):
    """Make a unique survey name for a given survey index.

    Parameters
    ----------
    scheduler : `rubin_scheduler.scheduler.schedulers.CoreScheduler`
        The scheduler instance.
    survey_index : `list` of `int`
        The index of the survey to name. If None, use the current survey.

    Returns
    -------
    survey_name : `str`
        A unique name for the survey.
    """
    if survey_index is None:
        survey_index = copy.deepcopy(scheduler.survey_index)

    # slice down through as many indexes as we have
    survey = scheduler.survey_lists
    for level_index in survey_index:
        survey = survey[level_index]

    try:
        survey_name = survey.survey_name
        if len(survey_name) < 1:
            survey_name = str(survey)
    except AttributeError:
        survey_name = str(survey)

    # For auxtel, different fields have the same survey_name, but
    # the interface should show the field name. So, if we're
    # getting a field name in scheduler_note or note, use that in addition to
    # the survey_name attribute.
    try:
        try:
            scheduler_note = f"{survey.observations['scheduler_note'][0]}"
        except KeyError:
            # The key used to be just "note". If "scheduler_note" is absent,
            # we may be following the older convention, so fall back on
            # that.
            scheduler_note = f"{survey.observations['note'][0]}"
    except (AttributeError, ValueError, TypeError, KeyError):
        scheduler_note = None

    if scheduler_note and scheduler_note not in survey_name:
        survey_name = f"{survey_name} ({scheduler_note})"

    survey_name = f"{survey_index[1]}: {survey_name}"

    # Bokeh tables have problems with < and >
    survey_name = survey_name.replace("<", "").replace(">", "")

    return survey_name


def make_scheduler_summary_df(scheduler, conditions, reward_df=None):
    """Summarize the reward from each scheduler

    Parameters
    ----------
    scheduler : `rubin_scheduler.scheduler.schedulers.CoreScheduler`
        The scheduler instance.
    conditions : `rubin_scheduler.scheduler.features.conditions.Conditions`
        The conditions for which to summarize the reward.
    reward_df : `pandas.DataFrame`
        The table with rewards for each survey. If None, calculate it.

    Returns
    -------
    survey_df : `pandas.DataFrame`
        A table showing the reword for each feasible survey, and the
        basis functions that result in it being infeasible for the rest.
    """
    if conditions is None:
        conditions = scheduler.conditions

    if reward_df is None:
        reward_df = scheduler.make_reward_df(conditions)

    summary_df = reward_df.reset_index()

    # Some oddball surveys do not have basis functions, but they still
    # need rows, so add fake basis functions to the summary_df for them.
    summary_df.set_index(["list_index", "survey_index"], inplace=True)
    for list_index, survey_list in enumerate(scheduler.survey_lists):
        for survey_index, survey in enumerate(survey_list):
            if (list_index, survey_index) not in summary_df.index:
                survey.calc_reward_function(conditions)
                summary_df.loc[(list_index, survey_index), "max_basis_reward"] = survey.reward
                summary_df.loc[(list_index, survey_index), "max_accum_reward"] = survey.reward
                summary_df.loc[(list_index, survey_index), "feasible"] = (
                    np.isfinite(survey.reward) or survey.reward > 0
                )
                summary_df.loc[(list_index, survey_index), "basis_function"] = "N/A"
    summary_df.reset_index(inplace=True)

    def make_tier_name(row):
        tier_name = f"tier {row.list_index}"
        return tier_name

    summary_df["tier"] = summary_df.apply(make_tier_name, axis=1)

    def get_survey_name(row):
        survey_name = make_unique_survey_name(scheduler, [row.list_index, row.survey_index])
        return survey_name

    summary_df["survey_name_with_id"] = summary_df.apply(get_survey_name, axis=1)

    standard_surveys = [c[0] for c in inspect.getmembers(surveys)]

    def get_survey_url(row):
        url_base = "https://rubin-scheduler.lsst.io/fbs-api-surveys.html"
        if isinstance(row.survey_class, str) and row.survey_class in standard_surveys:
            section_base = "rubin_scheduler.scheduler.surveys"
            survey_url = f"{url_base}#{section_base}.{row.survey_class}"
        else:
            generic_survey = "rubin_scheduler.scheduler.surveys.BaseSurvey"
            survey_url = f"{url_base}#{generic_survey}"
        return survey_url

    summary_df["survey_url"] = summary_df.apply(get_survey_url, axis=1)

    def make_survey_row(survey_bfs):
        infeasible_bf = ", ".join(survey_bfs.loc[~survey_bfs.feasible.astype(bool)].basis_function.to_list())
        infeasible = ~np.all(survey_bfs.feasible.astype(bool))
        reward = infeasible_bf if infeasible else survey_bfs.max_accum_reward.iloc[-1]
        if reward in (None, "N/A", "None"):
            reward = "Infeasible" if infeasible else "Feasible"

        survey_row = pd.Series({"reward": reward, "infeasible": infeasible})
        return survey_row

    survey_df = summary_df.groupby(
        ["list_index", "survey_index", "survey_name_with_id", "survey_url", "tier"]
    ).apply(make_survey_row)

    return survey_df["reward"].reset_index()
