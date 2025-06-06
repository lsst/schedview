from warnings import warn

import bokeh
import healpy as hp
import numpy as np
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory
from rubin_scheduler.scheduler.schedulers import CoreScheduler  # noqa F401
from uranography.api import ArmillarySphere, Planisphere, split_healpix_by_resolution

import schedview.compute.astro
from schedview import band_column
from schedview.collect import get_footprint, load_bright_stars, read_opsim
from schedview.compute.camera import LsstCameraFootprintPerimeter
from schedview.plot import PLOT_BAND_COLORS

NSIDE_LOW = 8


def add_footprint_to_skymaps(footprint, spheremaps):
    """Add the footprint to a skymap

    Parameters
    ----------
    footprint : `numpy.array`
        A healpix map of the footprint.
    spherermaps : `list` of `uranography.SphereMap`
        The map to add the footprint to
    """

    nside_low = NSIDE_LOW

    cmap = bokeh.transform.linear_cmap("value", "Greys256", int(np.ceil(np.nanmax(footprint) * 2)), 0)

    nside_high = hp.npix2nside(footprint.shape[0])
    footprint_high, footprint_low = split_healpix_by_resolution(footprint, nside_low, nside_high)

    healpix_high_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_high, nside=nside_high, cmap=cmap)
    healpix_low_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_low, nside=nside_low, cmap=cmap)

    for spheremap in spheremaps[1:]:
        spheremap.add_healpix(healpix_high_ds, nside=nside_high, cmap=cmap)
        spheremap.add_healpix(healpix_low_ds, nside=nside_low, cmap=cmap)

    return spheremaps
