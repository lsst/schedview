from collections import OrderedDict
from copy import deepcopy
from inspect import getmembers

import healpy as hp
import numpy as np
import rubin_sim.scheduler.basis_functions


def make_survey_reward_df(survey, conditions, reward_df=None):
    """Make a dataframe summarizing the rewards for a survey.

    Parameters
    ----------
    survey : `rubin_sim.scheduler.surveys.BaseSurvey`
        The survey to summarize.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`
        The conditions to use for the summary.
    reward_df : `pandas.DataFrame`, optional
        A dataframe with the columns "basis_function", "basis_function_class",
        "feasible", "max_basis_reward", "basis_area", "basis_weight",
        "max_accum_reward", and "accum_area".
        If not provided, this dataframe will be computed from the survey.

    Returns
    -------
    reward_df : `pandas.DataFrame`
        A dataframe with the columns "basis_function", "basis_function_class",
        "feasible", "max_basis_reward", "basis_area", "basis_weight",
        "max_accum_reward", "accum_area", and "doc_url".
    """

    if reward_df is None:
        reward_df = survey.make_reward_df(conditions)
    else:
        survey_reward_df_columns = [
            "basis_function",
            "basis_function_class",
            "feasible",
            "max_basis_reward",
            "basis_area",
            "basis_weight",
            "max_accum_reward",
            "accum_area",
        ]
        reward_df = reward_df[survey_reward_df_columns].reset_index(drop=True)

    def to_sigfig(x):
        return float("{:.5g}".format(x))

    def _guess_basis_function_doc_url(basis_function_name):
        if not isinstance(basis_function_name, str):
            return ""

        root_bf_name = basis_function_name.split()[0]

        standard_basis_functions = dict(getmembers(rubin_sim.scheduler.basis_functions)).keys()
        if root_bf_name in standard_basis_functions:
            url = f"https://rubin-sim.lsst.io/api/rubin_sim.scheduler.basis_functions.{root_bf_name}.html#rubin_sim.scheduler.basis_functions.{root_bf_name}"  # noqa E501
        else:
            url = ""
        return url

    try:
        reward_df["doc_url"] = reward_df["basis_function_class"].map(_guess_basis_function_doc_url)
    except KeyError:
        reward_df["doc_url"] = None

    for col in [
        "max_basis_reward",
        "basis_area",
        "max_accum_reward",
        "accum_area",
    ]:
        reward_df[col] = reward_df[col].apply(to_sigfig)

    return reward_df


def compute_maps(survey, conditions, nside=None):
    """Compute healpix maps associated with a survey under given conditions.

    Parameters
    ----------
    survey : `rubin_sim.scheduler.surveys.BaseSurvey`
        The survey to summarize.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`
        The conditions to use for the summary.
    nside : int, optional
        The nside to use for the returned healpix maps. If not provided, the
        nside from the conditions will be used.

    Returns
    -------
    survey_maps : `collections.OrderedDict`
        An ordered dictionary of healpix maps associated with the survey.
    """
    if nside is None:
        nside = conditions.nside

    survey_maps = OrderedDict()

    for band in conditions.skybrightness.keys():
        survey_maps[f"{band}_sky"] = deepcopy(conditions.skybrightness[band])

    def can_be_healpix_map(values):
        try:
            hp.pixelfunc.npix2nside(len(values))
            return True
        except (TypeError, ValueError):
            return False

    if hasattr(survey, "basis_functions"):
        for basis_function in survey.basis_functions:
            values = basis_function(conditions)
            if can_be_healpix_map(values):
                label = basis_function.label()
                base_label = label
                label_index = 1
                while label in survey_maps:
                    label_index += 1
                    label = f"{base_label} #{label_index}"

                survey_maps[label] = values

    values = survey.calc_reward_function(conditions)
    if not can_be_healpix_map(values):
        # values = np.fill(np.empty(hp.nside2npix(nside)), values)
        values = np.full(np.shape(np.empty(hp.nside2npix(nside))), -np.inf)

    survey_maps["reward"] = values

    # If a different nside was requested, change it for all maps
    for key in survey_maps:
        survey_maps[key][survey_maps[key] < -1e30] = hp.UNSEEN
        survey_maps[key][np.isnan(survey_maps[key])] = hp.UNSEEN
        survey_maps[key] = hp.pixelfunc.ud_grade(survey_maps[key], nside)
        survey_maps[key][survey_maps[key] == hp.UNSEEN] = np.nan

    return survey_maps
