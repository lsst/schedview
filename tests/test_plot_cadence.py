import unittest
from unittest import TestCase

import bokeh.models.layouts
import numpy as np
from rubin_sim.data import get_baseline

import schedview.collect
import schedview.compute.visits
from schedview.plot import create_cadence_plot

try:
    from rubin_sim import maf
except ModuleNotFoundError:
    pass


class TestPlotCadence(TestCase):

    @unittest.skipUnless("maf" in locals(), "No rubin_sim.maf installation")
    def test_create_cadence_plot(self):
        stackers = [
            maf.stackers.ObservationStartDatetime64Stacker(),
            maf.stackers.TeffStacker(),
            maf.stackers.DayObsISOStacker(),
        ]

        visit_db_fname = get_baseline()
        visits = schedview.collect.read_ddf_visits(visit_db_fname, stackers=stackers)
        night_totals = schedview.compute.visits.accum_teff_by_night(visits)
        start_dayobs_mjd = np.floor(visits.observationStartMJD.min())
        end_dayobs_mjd = start_dayobs_mjd + 365
        plot = create_cadence_plot(night_totals, start_dayobs_mjd, end_dayobs_mjd)
        self.assertIsInstance(plot, bokeh.models.layouts.LayoutDOM)
