import unittest

import astropy.utils.iers
import healpy as hp
from astropy.time import TimeDelta
from rubin_sim.scheduler.example import example_scheduler
from rubin_sim.scheduler.features.conditions import Conditions
from rubin_sim.scheduler.model_observatory import ModelObservatory

from schedview.collect import sample_pickle
from schedview.plot.scheduler import DEFAULT_MJD, SchedulerDisplay

NSIDE = 8
MJD_SCHED = DEFAULT_MJD
astropy.utils.iers.conf.iers_degraded_accuracy = "warn"


class TestSchedulerDisplay(unittest.TestCase):
    def test_scheduler_display(self):
        mjd = MJD_SCHED
        nside = NSIDE

        scheduler = example_scheduler(nside=nside, mjd_start=MJD_SCHED)

        try:
            observatory = ModelObservatory(mjd_start=mjd - 1, nside=nside)
            observatory.mjd = mjd
            conditions = observatory.return_conditions()
        except ValueError:
            # If we do not have the right cache of sky brightness
            # values on disk, we may not be able to instantiate
            # ModelObservatory, but we should be able to run
            # it anyway. Fake up a conditions object as well as
            # we can.
            conditions = Conditions(mjd_start=mjd - 1, nside=nside)
            conditions.mjd = mjd

        scheduler.update_conditions(conditions)
        scheduler.request_observation()

        sched_display = SchedulerDisplay(nside=NSIDE, scheduler=scheduler)
        self.assertTrue(sched_display.scheduler is scheduler)

        # Drives the creation of many bokeh models
        sched_display.make_figure()

        self.assertGreater(len(sched_display.map_keys), 0)

        self.assertEqual(sched_display.mjd, MJD_SCHED)
        self.assertLessEqual(sched_display.conditions.sun_n18_setting, MJD_SCHED)
        self.assertGreaterEqual(sched_display.conditions.sun_n18_rising, MJD_SCHED)

        new_mjd = MJD_SCHED + 1.1
        sched_display.mjd = new_mjd
        self.assertEqual(sched_display.mjd, new_mjd)
        self.assertLessEqual(sched_display.conditions.sun_n18_setting, new_mjd)
        self.assertGreaterEqual(sched_display.conditions.sun_n18_rising, new_mjd)

        time = sched_display.time
        prev_mjd = sched_display.mjd
        time_change = TimeDelta(1.8, format="jd")
        next_time = time + time_change
        sched_display.time = next_time
        self.assertAlmostEqual(sched_display.mjd, prev_mjd + time_change.value)

        hp_values = sched_display.healpix_values
        self.assertEqual(hp.nside2npix(NSIDE), hp_values.shape[0])
        self.assertEqual(len(hp_values.shape), 1)

        pre_load_conditions = sched_display.conditions
        pre_load_scheduler = sched_display.scheduler
        self.assertTrue(sched_display.scheduler is pre_load_scheduler)
        self.assertTrue(sched_display.conditions is pre_load_conditions)
        file_name = sample_pickle()
        sched_display.load(file_name)
        self.assertTrue(sched_display.scheduler is not pre_load_scheduler)
        self.assertTrue(sched_display.conditions is not pre_load_conditions)

        new_survey_index = 1
        sched_display.select_survey(sched_display.surveys_in_tier[new_survey_index])
        self.assertEqual(sched_display.survey_index[1], new_survey_index)

        new_tier = sched_display.tier_names[1]
        sched_display.select_tier(new_tier)
        self.assertSequenceEqual(sched_display.survey_index, [1, 0])

        sched_display.select_value(sched_display.map_keys[0])
        self.assertEqual(sched_display.map_key, sched_display.map_keys[0])
        sched_display.select_value(sched_display.map_keys[1])
        self.assertEqual(sched_display.map_key, sched_display.map_keys[1])


if __name__ == "__main__":
    unittest.main()
