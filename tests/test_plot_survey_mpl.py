import datetime

import astropy
import healpy as hp
import numpy as np
from astropy.time import Time
from lsst.resources import ResourcePath
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview
import schedview.collect
from schedview.plot.survey_mpl import create_hpix_visit_map_grid, map_visits_over_healpix

RANDOM_SEED = 6563


def test_map_visits_over_healpix():
    hp_map = np.random.default_rng(RANDOM_SEED).uniform(0, 1, hp.nside2npix(4))

    visits_path = ResourcePath("resource://schedview/data/sample_opsim.db")
    visits = schedview.collect.read_opsim(visits_path)
    visits_mjd = visits["observationStartMJD"].median()
    time_datetime = Time(visits_mjd - 0.5, format="mjd").datetime

    model_observatory = ModelObservatory(init_load_length=1)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    night_events = schedview.compute.astro.night_events(
        datetime.date(time_datetime.year, time_datetime.month, time_datetime.day)
    )

    map_visits_over_healpix(visits, hp_map, model_observatory, night_events)


def test_create_hpix_visit_map_grid():
    hpix_maps = {}
    for band in "ugrizy":
        hpix_maps[band] = np.random.default_rng(RANDOM_SEED).uniform(0, 1, hp.nside2npix(4))

    visits_path = ResourcePath("resource://schedview/data/sample_opsim.db")
    visits = schedview.collect.read_opsim(visits_path)
    visits_mjd = visits["observationStartMJD"].median()
    time_datetime = Time(visits_mjd - 0.5, format="mjd").datetime

    model_observatory = ModelObservatory(init_load_length=1)
    astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"
    night_events = schedview.compute.astro.night_events(
        datetime.date(time_datetime.year, time_datetime.month, time_datetime.day)
    )

    create_hpix_visit_map_grid(visits, hpix_maps, model_observatory, night_events)
