import numpy as np
from rubin_sim.scheduler.utils.sky_area import SkyAreaGenerator


def get_footprint(scheduler=None):
    """Extract the footprint from a survey."""
    # This is a hack, good enough for example code, not for production.

    # Look through the scheduler to find a blob survey that has a footprint
    # basis function
    footprint = None
    if scheduler is None:
        nside = 32
    else:
        nside = scheduler.nside
        for survey_tier in scheduler.survey_lists:
            for survey in survey_tier:
                if survey.__class__.__name__ in ["GreedySurvey"]:
                    for basis_function in survey.basis_functions:
                        bf_class = basis_function.__class__
                        if bf_class.__name__.startswith("Footprint"):
                            if footprint is None:
                                footprint = np.sum(basis_function.footprint.footprints, axis=0)
                            else:
                                footprint += np.sum(basis_function.footprint.footprints, axis=0)

    if footprint is None:
        sky_area_generator = SkyAreaGenerator(nside=nside)
        band_footprints, _ = sky_area_generator.return_maps()
        footprint = np.sum(band_footprints[b] for b in band_footprints.dtype.fields.keys())

    footprint[footprint == 0] = np.nan
    return footprint
