from unittest import TestCase

import bokeh.models.layouts
import numpy as np
from rubin_scheduler.data import get_baseline

import schedview.collect
import schedview.compute.visits
from schedview.plot import create_cadence_plot


class TestPlotCadence(TestCase):

    def test_create_cadence_plot(self):
        visit_db_fname = get_baseline()
        visits = schedview.collect.read_ddf_visits(visit_db_fname)
        night_totals = schedview.compute.visits.accum_teff_by_night(visits)
        start_dayobs_mjd = np.floor(visits.observationStartMJD.min())
        end_dayobs_mjd = start_dayobs_mjd + 365
        plot = create_cadence_plot(night_totals, start_dayobs_mjd, end_dayobs_mjd)
        self.assertIsInstance(plot, bokeh.models.layouts.LayoutDOM)
