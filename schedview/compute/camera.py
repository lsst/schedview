import astropy.units as u
import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord


class LsstCameraFootprintPerimeter(object):
    """Compute vertices surrounding the LSST camera footprint."""

    footprint_wide_rafts = 5
    footprint_thin_rafts = 3
    footprint_width_deg = 3.5

    def __init__(self):
        raft_width_deg = self.footprint_width_deg / self.footprint_wide_rafts

        offsets = (
            0,
            raft_width_deg,
            self.footprint_width_deg - raft_width_deg,
            self.footprint_width_deg,
        )
        self.vertices = pd.DataFrame(
            {
                "x": [
                    offsets[i] - self.footprint_width_deg / 2 for i in (0, 1, 1, 2, 2, 3, 3, 2, 2, 1, 1, 0, 0)
                ],
                "y": [
                    offsets[i] - self.footprint_width_deg / 2 for i in (2, 2, 3, 3, 2, 2, 1, 1, 0, 0, 1, 1, 2)
                ],
            }
        )
        self.vertices["angle"] = np.degrees(np.arctan2(self.vertices.y, self.vertices.x))
        self.vertices["r"] = np.hypot(self.vertices.y, self.vertices.x)

    def single_eq_vertices(self, ra, decl, rotation=0):
        """Compute vertices for a single pair of equatorial coordinates

        Parameters
        ----------
        ra : `float`
            The R.A. (in degrees)
        decl : `float`
            The declination (in degrees)
        rotation : `float`
            The camera rotation (in degrees)

        Returns
        -------
        ra : `numpy.ndarray`
            An array of the R.A. of the vertices of the polygon surrounding
            the camera footprint (degrees).
        decl : `numpy.ndarray`
            An array of the declinations of the vertices of the polygon
            surrounding the camera footprint (degrees).
        """
        center = SkyCoord(ra, decl, unit="deg")

        # rotation matches the sense used by
        # rubin_sim.utils.camera_footprint.LsstCameraFootprint
        eq_vertices = center.directional_offset_by(
            (self.vertices.angle.values + rotation) * u.deg,
            self.vertices.r.values * u.deg,
        )
        ra = eq_vertices.ra.deg
        decl = eq_vertices.dec.deg
        return ra, decl

    def __call__(self, ra, decl, rotation=0):
        """Compute vertices for a single pair of equatorial coordinates

        Parameters
        ----------
        ra : `np.ndarray`
            The R.A. of pointings (in degrees)
        decl : `np.ndarray`
            The declination of pointings (in degrees)
        rotation : `float` or `np.ndarray`
            The camera rotation(s) (in degrees)

        Returns
        -------
        ra : `numpy.ndarray`
            An array of the R.A. of the vertices of the polygon surrounding
            the camera footprints (degrees).
        decl : `numpy.ndarray`
            An array of the declinations of the vertices of the polygon
            surrounding the camera footprints (degrees).
        """
        if np.isscalar(ra):
            return self.single_eq_vertices(ra, decl, rotation)

        if np.isscalar(rotation):
            rotation = np.full_like(ra, rotation)

        vertex_ras, vertex_decls = [], []
        for this_ra, this_decl, this_rotation in zip(ra, decl, rotation):
            this_vertex_ra, this_vertex_decl = self.single_eq_vertices(this_ra, this_decl, this_rotation)
            vertex_ras.append(this_vertex_ra)
            vertex_decls.append(this_vertex_decl)

        return vertex_ras, vertex_decls
