import numpy as np
from rubin_scheduler.scheduler.utils import CurrentAreaMap


def get_footprint(nside=32):
    """Get the survey footprint."""

    # Load up a default footprint from rubin_scheduler
    sky_area_generator = CurrentAreaMap(nside=nside)
    band_footprints, _ = sky_area_generator.return_maps()
    footprint = np.sum(band_footprints[b] for b in band_footprints.dtype.fields.keys())

    footprint[footprint == 0] = np.nan
    return footprint
