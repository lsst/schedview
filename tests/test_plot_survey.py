import unittest

import healpy as hp
import numpy as np
from uranography.api import SphereMap

from schedview.plot.survey import map_survey_healpix

RANDOM_NUMBER_GENERATOR = np.random.default_rng(6563)


class TestComputeSurvey(unittest.TestCase):
    def test_map_survey_healpix(self):
        nside = 8
        npix = hp.nside2npix(nside)
        survey_maps = {k: RANDOM_NUMBER_GENERATOR.random(npix) for k in "abc"}
        sky_map = map_survey_healpix(60200, survey_maps, "a", nside=nside)
        self.assertIsInstance(sky_map, SphereMap)
