import numpy as np

def get_greedy_footprint(scheduler):
    """Extract the footprint from a survey."""
    # This is a hack, good enough for example code, not for production.

    # Look through the scheduler to find a blob survey that has a footprint basis function
    for survey_tier in scheduler.survey_lists:
        for survey in survey_tier:
            if survey.__class__.__name__ in ["Greedy_survey"]:
                for basis_function in survey.basis_functions:
                    if basis_function.__class__.__name__.startswith("Footprint"):
                        try:
                            footprint += np.sum(basis_function.footprint.footprints, axis=0)
                        except NameError:
                            footprint = np.sum(basis_function.footprint.footprints, axis=0)

    footprint[footprint == 0] = np.nan
    return footprint
