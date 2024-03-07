import datetime

import astropy
import astropy.units as u
import healpy as hp
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview.compute.astro
from schedview.plot.mplutils import (
    LAEA_SOUTH,
    compute_circle_points,
    map_healpix,
    plot_ecliptic,
    plot_galactic_plane,
    plot_horizons,
    plot_moon,
    plot_sun,
    sky_map,
)

RANDOM_SEED = 6563


def test_compute_circle_points():
    center_ra, center_decl = 32.2, 10.3
    radius = 12.2
    circle_points = compute_circle_points(
        center_ra,
        center_decl,
        radius=radius,
        start_bear=0,
        end_bear=360,
        step=1,
    )

    center_coords = SkyCoord(center_ra, center_decl, unit=u.deg)
    circle_coords = SkyCoord(circle_points.ra, circle_points.decl, unit=u.deg)
    angles = center_coords.separation(circle_coords)
    np.testing.assert_almost_equal(angles.deg, radius)
    bearings = center_coords.position_angle(circle_coords)
    np.testing.assert_almost_equal(circle_points.reset_index().bearing, bearings.deg)


def test_sky_map():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    sky_map(axes)


def test_map_healpix():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    hp_map = np.random.default_rng(RANDOM_SEED).uniform(0, 1, hp.nside2npix(4))
    map_healpix(axes, hp_map)


def test_plot_ecliptic():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    plot_ecliptic(axes)


def test_plot_galactic_plane():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    plot_galactic_plane(axes)


def test_plot_sun():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    model_observatory = ModelObservatory(init_load_length=1)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    night_events = schedview.compute.astro.night_events(datetime.date(2025, 1, 1))
    plot_sun(axes, model_observatory, night_events)


def test_plot_moon():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    model_observatory = ModelObservatory(init_load_length=1)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    night_events = schedview.compute.astro.night_events(datetime.date(2025, 1, 1))
    plot_moon(axes, model_observatory, night_events)


def test_plot_horizons():
    figure = plt.figure()
    axes = figure.add_subplot(projection=LAEA_SOUTH)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    night_events = schedview.compute.astro.night_events(datetime.date(2025, 1, 1))
    plot_horizons(axes, night_events, -32, 80)
