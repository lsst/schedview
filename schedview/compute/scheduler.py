import numpy as np
import pandas as pd
from astropy.timeseries import TimeSeries
from astropy.time import Time
from rubin_sim.scheduler.utils import empty_observation
from rubin_sim.scheduler.model_observatory import ModelObservatory


def _make_observation_from_record(record):
    """Convert an opsim visit record to a scheduler observation

    Parameters
    ----------
    record : `dict`
        A row from an opsim output table

    Returns
    -------
    observation : `numpy.ndarray`
        A numpy recarray with data understood by the scheduler
    """
    observation = empty_observation()
    observation["RA"] = np.radians(record["fieldRA"])
    observation["dec"] = np.radians(record["fieldDec"])
    observation["mjd"] = record["observationStartMJD"]
    observation["flush_by_mjd"] = record["flush_by_mjd"]
    observation["exptime"] = record["visitExposureTime"]
    observation["filter"] = record["filter"]
    observation["rotSkyPos"] = np.radians(record["rotSkyPos"])
    observation["rotSkyPos_desired"] = np.radians(record["rotSkyPos_desired"])
    observation["nexp"] = record["numExposures"]
    observation["airmass"] = record["airmass"]
    observation["FWHM_500"] = record["seeingFwhm500"]
    observation["FWHMeff"] = record["seeingFwhmEff"]
    observation["FWHM_geometric"] = record["seeingFwhmGeom"]
    observation["skybrightness"] = record["skyBrightness"]
    observation["night"] = record["night"]
    observation["slewtime"] = record["slewTime"]
    observation["visittime"] = record["visitTime"]
    observation["slewdist"] = np.radians(record["slewDistance"])
    observation["fivesigmadepth"] = record["fiveSigmaDepth"]
    observation["alt"] = np.radians(record["altitude"])
    observation["az"] = np.radians(record["azimuth"])
    observation["pa"] = np.radians(record["paraAngle"])
    observation["clouds"] = record["cloud"]
    observation["moonAlt"] = np.radians(record["moonAlt"])
    observation["sunAlt"] = np.radians(record["sunAlt"])
    observation["note"] = record["note"]
    observation["field_id"] = record["fieldId"]
    observation["survey_id"] = record["proposalId"]
    observation["block_id"] = record["block_id"]
    observation["lmst"] = record["observationStartLST"] / 15
    observation["rotTelPos"] = np.radians(record["rotTelPos"])
    observation["rotTelPos_backup"] = np.radians(record["rotTelPos_backup"])
    observation["moonAz"] = np.radians(record["moonAz"])
    observation["sunAz"] = np.radians(record["sunAz"])
    observation["sunRA"] = np.radians(record["sunRA"])
    observation["sunDec"] = np.radians(record["sunDec"])
    observation["moonRA"] = np.radians(record["moonRA"])
    observation["moonDec"] = np.radians(record["moonDec"])
    observation["moonDist"] = np.radians(record["moonDistance"])
    observation["solarElong"] = np.radians(record["solarElong"])
    observation["moonPhase"] = record["moonPhase"]
    observation["cummTelAz"] = np.radians(record["cummTelAz"])
    observation["scripted_id"] = record["scripted_id"]
    return observation


def replay_visits(scheduler, visits):
    """Update a scheduler instances with a set of visits.

    Parameters
    ----------
    scheduler : `rubin_sim.scheduler.CoreScheduler`
        An instance of the scheduler to update
    visits : `pandas.DataFrame`
        A table of visits to add.
    """
    for visit_id, visit_record in visits.iterrows():
        obs = _make_observation_from_record(visit_record)
        scheduler.add_observation(obs)

    scheduler.conditions.mjd = float(
        obs["mjd"] + (obs["slewtime"] + obs["visittime"]) / (24 * 60 * 60)
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
        survey_name = scheduler.survey_lists[row.list_index][
            row.survey_index
        ].survey_name
        if len(survey_name) == 0:
            class_name = scheduler.survey_lists[row.list_index][
                row.survey_index
            ].__class__.__name__
            survey_name = f"{class_name}_{row.list_index}_{row.survey_index}"
        return survey_name

    summary_df["survey_name"] = summary_df.apply(get_survey_name, axis=1)

    def make_survey_row(survey_bfs):
        infeasible_bf = ", ".join(
            survey_bfs.loc[~survey_bfs.feasible.astype(bool)].basis_function.to_list()
        )
        infeasible = ~np.all(survey_bfs.feasible.astype(bool))
        list_index = survey_bfs.list_index.iloc[0]
        survey_index = survey_bfs.survey_index.iloc[0]
        direct_reward = scheduler.survey_lists[list_index][
            survey_index
        ].calc_reward_function(conditions)
        reward = survey_bfs.accum_reward.iloc[-1]

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
            Time(
                float(scheduler.conditions.sun_n12_setting), format="mjd", scale="utc"
            ).datetime,
            Time(
                float(scheduler.conditions.sun_n12_rising), format="mjd", scale="utc"
            ).datetime,
            freq="10T",
        )

    if isinstance(sample_times, TimeSeries):
        sample_times = sample_times.to_pandas()

    reward_list = []
    for time in sample_times:
        this_time_reward = compute_basis_function_reward_at_time(
            scheduler, time, observatory
        )
        this_time_reward["mjd"] = Time(time).mjd
        this_time_reward["time"] = time
        reward_list.append(this_time_reward)

    rewards = pd.concat(reward_list).reset_index()

    return rewards
