import unittest

import numpy as np
import pandas as pd

from schedview.compute.astro import compute_central_night, night_events

TEST_MJDS = [60000.6, 60000.8, 60001.2]


class TestComputeAstro(unittest.TestCase):
    def test_compute_central_night(self):
        for mjd in TEST_MJDS:
            visits = pd.DataFrame(
                {
                    "observationStartMJD": [mjd - 0.1, mjd, mjd + 0.1],
                    "fieldRA": [0, 0, 0],
                    "fieldDec": [0, 0, 0],
                    "filter": ["r", "i", "z"],
                }
            )
            computed_night = compute_central_night(visits)
            computed_night_events = night_events(computed_night)
            computed_night_middle_mjd = computed_night_events.loc["night_middle", "MJD"]
            assert np.abs(computed_night_middle_mjd - mjd) <= 0.5
