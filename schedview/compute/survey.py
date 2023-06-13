import rubin_sim.scheduler.basis_functions
from inspect import getmembers


def make_survey_reward_df(survey, conditions, reward_df=None):

    if reward_df is None:
        reward_df = survey.make_reward_df(conditions)

    def to_sigfig(x):
        return float("{:.5g}".format(x))

    def _guess_basis_function_doc_url(basis_function_name):
        if not isinstance(basis_function_name, str):
            return ""

        root_bf_name = basis_function_name.split()[0]

        standard_basis_functions = dict(
            getmembers(rubin_sim.scheduler.basis_functions)
        ).keys()
        if root_bf_name in standard_basis_functions:
            url = f"https://rubin-sim.lsst.io/api/rubin_sim.scheduler.basis_functions.{root_bf_name}.html#rubin_sim.scheduler.basis_functions.{root_bf_name}"  # noqa E501
        else:
            url = ""
        return url

    try:
        reward_df["doc_url"] = reward_df["basis_function_class"].map(
            _guess_basis_function_doc_url
        )
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
