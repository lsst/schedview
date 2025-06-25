import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import bokeh.plotting
import healpy as hp
import numpy as np
from rubin_scheduler.scheduler.utils import get_current_footprint
from uranography.api import ArmillarySphere, Planisphere

import schedview.compute.footprint

NSIDE = 16


class TestFootprint(unittest.TestCase):

    def test_find_healpix_area_polygons(self):
        footprint_regions = get_current_footprint(NSIDE)[1]
        footprint_polygons = schedview.compute.footprint.find_healpix_area_polygons(footprint_regions)

        # Make sure we have a reasonable number of regions, but make sure we
        # can still pass the test if the footprint varies reasonably.
        assert 5 < len(footprint_polygons.index.get_level_values("region").unique()) < 100

        # Make sure there are a reasonable number of vertexes in each loop,
        # even if we use a low nside to make the test fast.
        # Each healpix has 4 vertexes, so less than 4 or more than 4*npix is
        # clearly a bug.
        number_in_loops = footprint_polygons.assign(n=1).groupby(["region", "loop"]).agg({"n": "sum"}).n
        assert np.all(number_in_loops >= 4)
        assert np.all(number_in_loops < 4 * hp.nside2npix(NSIDE))

        # Make sure all coordinates are in expected ranges.
        assert np.all(360 >= footprint_polygons.loc[:, "RA"])
        assert np.all(0 <= footprint_polygons.loc[:, "RA"])
        assert np.all(60 > footprint_polygons.loc[:, "decl"])
        assert np.all(-90 <= footprint_polygons.loc[:, "decl"])
        for coord in "xyz":
            assert np.all(footprint_polygons.loc[:, coord] <= 1)
            assert np.all(footprint_polygons.loc[:, coord] >= -1)

    def test_add_footprint_to_skymaps(self):
        footprint = get_current_footprint(NSIDE)[0]["g"]
        psphere = Planisphere()
        asphere = ArmillarySphere()
        schedview.plot.footprint.add_footprint_to_skymaps(footprint, [asphere, psphere])

        with TemporaryDirectory() as test_dir:
            test_path = Path(test_dir)
            test_fname = test_path.joinpath("test_add_footprint_to_skymaps.html")
            fig = bokeh.layouts.row([psphere.figure, asphere.figure])
            bokeh.plotting.output_file(filename=test_fname, title="This Test Page")
            bokeh.plotting.save(fig)

    def test_add_footprint_outlines_to_skymaps(self):
        footprint_regions = get_current_footprint(NSIDE)[1]
        footprint_polygons = schedview.compute.footprint.find_healpix_area_polygons(footprint_regions)
        psphere = Planisphere()
        asphere = ArmillarySphere()
        schedview.plot.footprint.add_footprint_outlines_to_skymaps(footprint_polygons, [asphere, psphere])

        with TemporaryDirectory() as test_dir:
            test_path = Path(test_dir)
            test_fname = test_path.joinpath("test_add_footprint_outlines_to_skymaps.html")
            fig = bokeh.layouts.row([psphere.figure, asphere.figure])
            bokeh.plotting.output_file(filename=test_fname, title="This Test Page")
            bokeh.plotting.save(fig)
