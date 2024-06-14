import unittest

import bokeh
import healpy as hp
import numpy as np
from astropy.time import Time
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.utils import survey_start_mjd
from rubin_sim.data import get_baseline
from uranography.api import SphereMap

import schedview.collect
from schedview.plot.survey import create_hpix_visit_map_grid, map_survey_healpix, map_visits_over_hpix

RANDOM_NUMBER_GENERATOR = np.random.default_rng(6563)
TEST_MJD = survey_start_mjd() + 0.2


class TestMapSurvey(unittest.TestCase):
    def test_map_survey_healpix(self):
        nside = 8
        npix = hp.nside2npix(nside)
        survey_maps = {k: RANDOM_NUMBER_GENERATOR.random(npix) for k in "abc"}
        sky_map = map_survey_healpix(TEST_MJD, survey_maps, "a", nside=nside)
        self.assertIsInstance(sky_map, SphereMap)

    def test_create_hpix_visit_map_grid(self):
        nside = 8
        npix = hp.nside2npix(nside)
        hpix_maps = {b: RANDOM_NUMBER_GENERATOR.random(npix) for b in "ugrizy"}

        start_mjd = survey_start_mjd()
        visits = schedview.collect.read_opsim(
            get_baseline(), Time(start_mjd + 0.5, format="mjd"), Time(start_mjd + 1.5, format="mjd")
        )

        observatory = ModelObservatory(mjd_start=start_mjd + 1, nside=nside)
        conditions = observatory.return_conditions()

        plot = create_hpix_visit_map_grid(hpix_maps, visits, conditions)
        self.assertIsInstance(plot, bokeh.models.plots.GridPlot)

    def test_create_hpix_visit_map_no_raster(self):
        nside = 8
        npix = hp.nside2npix(nside)
        hpix_map = RANDOM_NUMBER_GENERATOR.random(npix)

        start_mjd = survey_start_mjd()
        visits = schedview.collect.read_opsim(
            get_baseline(), Time(start_mjd + 0.5, format="mjd"), Time(start_mjd + 1.5, format="mjd")
        )

        observatory = ModelObservatory(mjd_start=start_mjd + 1, nside=nside)
        conditions = observatory.return_conditions()

        plot = map_visits_over_hpix(visits, conditions, hpix_map, prerender_hpix=False)
        self.assertIsInstance(plot, bokeh.models.plots.Plot)
