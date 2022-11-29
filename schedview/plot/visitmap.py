import numpy as np
import healpy as hp
import bokeh
from schedview.plot.SphereMap import Planisphere, ArmillarySphere

BAND_COLORS = dict(
    u="#56b4e9", g="#008060", r="#ff4000", i="#850000", z="#6600cc", y="#000000"
)


def visit_skymaps(visits, footprint, conditions):

    band_sizes = {"u": 15, "g": 13, "r": 11, "i": 9, "z": 7, "y": 5}

    psphere = Planisphere(mjd=conditions.mjd)

    asphere = ArmillarySphere(mjd=conditions.mjd)
    cmap = bokeh.transform.linear_cmap(
        "value", "Greys256", int(np.ceil(np.nanmax(footprint) * 2)), 0
    )
    nside = hp.npix2nside(footprint.shape[0])
    healpix_ds, cmap, glyph = asphere.add_healpix(footprint, nside=nside, cmap=cmap)
    psphere.add_healpix(healpix_ds, nside=nside, cmap=cmap)
    for band in "ugrizy":
        band_visits = visits.query(f"filter == '{band}'")
        visit_ds = asphere.add_marker(
            ra=band_visits.fieldRA,
            decl=band_visits.fieldDec,
            glyph_size=band_sizes[band],
            name=band_visits.index.values,
            min_mjd=band_visits.observationStartMJD.values,
            circle_kwargs={
                "fill_alpha": "in_mjd_window",
                "fill_color": BAND_COLORS[band],
                "line_alpha": 0,
            },
        )
        psphere.add_marker(
            data_source=visit_ds,
            glyph_size=band_sizes[band],
            name=band_visits.index.values,
            min_mjd=band_visits.observationStartMJD.values,
            circle_kwargs={
                "fill_alpha": "in_mjd_window",
                "fill_color": BAND_COLORS[band],
                "line_alpha": 0,
            },
        )
    asphere.decorate()
    psphere.decorate()
    horizon_ds = asphere.add_horizon()
    psphere.add_horizon(data_source=horizon_ds)
    horizon70_ds = asphere.add_horizon(
        zd=70, line_kwargs={"color": "red", "line_width": 2}
    )
    psphere.add_horizon(
        data_source=horizon70_ds, line_kwargs={"color": "red", "line_width": 2}
    )
    sun_ds = asphere.add_marker(
        ra=np.degrees(conditions.sunRA),
        decl=np.degrees(conditions.sunDec),
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )
    psphere.add_marker(
        data_source=sun_ds,
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )

    moon_ds = asphere.add_marker(
        ra=np.degrees(conditions.moonRA),
        decl=np.degrees(conditions.moonDec),
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )
    psphere.add_marker(
        data_source=moon_ds,
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )

    asphere.sliders["mjd"].start = conditions.sun_n12_setting
    asphere.sliders["mjd"].end = conditions.sun_n12_rising

    fig = bokeh.layouts.row(
        asphere.figure,
        psphere.figure,
    )
    return fig
