import re

import astropy
import bokeh
import numpy as np
import rubin_sim.scheduler.features.conditions
import rubin_sim.scheduler.surveys  # noqa: F401
from astropy.time import Time
from uranography.api import HorizonMap, make_zscale_linear_cmap


def map_survey_healpix(
    mjd,
    hpix_data,
    map_key,
    nside,
    map_class=HorizonMap,
    map_kwargs=None,
    cmap=None,
    cmap_scale="full",
    conditions=None,
    survey=None,
):
    """Map a healpix map of a survey at a given MJD.

    Parameters
    ----------
    mjd : `float`
        The MJD at which to map the survey.
    hpix_data : `dict`
        A dictionary of healpix maps. The map with `map_key` will be mapped
        to pixel color, and others will be shown in the hover tool.
    map_key : `str`
        The key in hpix_data corresponding to the healpix map to display.
    nside : `int`
        The nside at which to show the healpix maps.
    map_class : `class`, optional
        The class of map to use.  Defaults to uranography.HorizonMap.
    map_kwargs : `dict`, optional
        Keyword arguments to pass to map_class.
    cmap : `bokeh.models.mappers.ColorMapper`, optional
        A color mapper to use for the map.  Defaults to a linear cmap with the
        "Inferno256" palette.
    cmap_scale : `str`, optional
        The scale to use for the cmap.  Defaults to "full", which uses the full
        range of values in the healpix map.  Alternatively, "zscale" can be
        used to use a zscale cmap.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`, optional
        Default is None.
        The observing conditions at which to map the survey, used to determine
        telescope pointing. If None, do not mark telescope pointing.
    survey : `rubin_sim.scheduler.surveys.BaseSurvey`, optional
        Default is None.
        The survey with fields to mark on the map.
        If None or an unsuitable survey type, do not mark survey fields.

    Returns
    -------
    sky_map : `uranography.SphereMap`
        The map of the sky.
    """
    if map_kwargs is None:
        map_kwargs = {}

    sun_coords = astropy.coordinates.get_body("sun", Time(mjd, format="mjd"))
    moon_coords = astropy.coordinates.get_body("moon", Time(mjd, format="mjd"))

    sky_map = map_class(mjd=mjd, **map_kwargs)
    sky_map.sliders["mjd"].visible = False

    if cmap is None:
        min_good_value = np.nanmin(hpix_data[map_key])
        max_good_value = np.nanmax(hpix_data[map_key])
        if min_good_value == max_good_value:
            cmap = bokeh.transform.linear_cmap(
                "value",
                "Greys256",
                min_good_value - 1,
                max_good_value + 1,
            )
        elif cmap_scale == "full":
            cmap = bokeh.transform.linear_cmap(
                "value",
                "Inferno256",
                np.nanmin(hpix_data[map_key]),
                np.nanmax(hpix_data[map_key]),
            )
        elif cmap_scale == "zscale":
            make_zscale_linear_cmap(hpix_data[map_key])
        else:
            raise ValueError(f"Unrecognized cmap_scale: {cmap_scale}")

    sky_map.add_healpix(
        hpix_data[map_key],
        nside=nside,
        cmap=cmap,
        ds_name="hpix_ds",
        name="hpix_renderer",
    )

    sky_map.add_horizon_graticules()
    sky_map.add_ecliptic()
    sky_map.add_galactic_plane()

    sky_map.add_marker(
        sun_coords.ra.deg,
        sun_coords.dec.deg,
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "brown"},
    )
    sky_map.add_marker(
        moon_coords.ra.deg,
        moon_coords.dec.deg,
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange"},
    )

    # Add the hovertool
    hpix_datasource = sky_map.plot.select(name="hpix_ds")[0]
    hpix_renderer = sky_map.plot.select(name="hpix_renderer")[0]
    shown_hpix_data = dict(hpix_datasource.data)
    shown_hpids = shown_hpix_data["hpid"]
    tooltips = [
        (f"hpid (nside={nside})", "@hpid"),
        ("R. A. (deg)", "@center_ra"),
        ("Declination (deg)", "@center_decl"),
    ]

    if conditions is not None and conditions.tel_az is not None and conditions.tel_alt is not None:
        telescope_marker_data_source = bokeh.models.ColumnDataSource(
            data={
                "az": [np.degrees(conditions.tel_az)],
                "alt": [np.degrees(conditions.tel_alt)],
                "name": ["telescope_pointing"],
                "glyph_size": [20],
            },
            name="telescope_pointing",
        )

        sky_map.add_marker(
            data_source=telescope_marker_data_source,
            name="telescope_pointing_marker",
            circle_kwargs={"color": "green", "fill_alpha": 0.5},
        )

    if survey is not None:
        try:
            survey_field_data_source = bokeh.models.ColumnDataSource(
                data={
                    "ra": list(survey.ra_deg),
                    "decl": list(survey.dec_deg),
                    "name": ["survey_pointing {i}" for i, ra in enumerate(list(survey.ra_deg))],
                    "glyph_size": [20] * len(list(survey.ra_deg)),
                },
                name="survey_pointings",
            )
            sky_map.add_marker(
                data_source=survey_field_data_source,
                name="survey_field_marker",
                circle_kwargs={"color": "black", "fill_alpha": 0},
            )
        except AttributeError:
            pass

    # If we have alt/az coordinates, include them
    if "x_hz" in shown_hpix_data.keys() and "y_hz" in shown_hpix_data.keys():
        x_hz = np.mean(np.array(shown_hpix_data["x_hz"]), axis=1)
        y_hz = np.mean(np.array(shown_hpix_data["y_hz"]), axis=1)

        zd = np.degrees(np.sqrt(x_hz**2 + y_hz**2))
        alt = 90 - zd
        az = np.degrees(np.arctan2(-x_hz, y_hz))

        # Calculate airmass using Kirstensen (1998), good to the horizon.
        # Models the atmosphere with a uniform spherical shell with a height
        # 1/470 of the radius of the earth.
        # https://doi.org/10.1002/asna.2123190313
        a_cos_zd = 470 * np.cos(np.radians(zd))
        airmass = np.sqrt(a_cos_zd**2 + 941) - a_cos_zd

        if "zd" not in shown_hpix_data and "zd" not in hpix_data:
            shown_hpix_data["zd"] = zd
            tooltips.append(("Zenith Distance (deg)", "@zd"))

        if "alt" not in shown_hpix_data and "alt" not in hpix_data:
            shown_hpix_data["alt"] = alt
            tooltips.append(("Altitude (deg)", "@alt"))

        if "azimuth" not in shown_hpix_data and "azimuth" not in hpix_data:
            shown_hpix_data["azimuth"] = az
            tooltips.append(("Azimuth (deg)", "@azimuth"))

        if "airmass" not in shown_hpix_data and "airmass" not in hpix_data:
            shown_hpix_data["airmass"] = airmass
            tooltips.append(("airmass", "@airmass"))

        sky_map.add_horizon(89.99, line_kwargs={"color": "black", "line_width": 2})
        sky_map.add_horizon(70, line_kwargs={"color": "red", "line_width": 2})

    for key in hpix_data:
        column_name = key.replace(" ", "_").replace(".", "_").replace("@", "_")
        shown_hpix_data[column_name] = hpix_data[key][shown_hpids]
        label = re.sub(" @[0-9]*$", "", key)
        tooltips.append((label, f"@{column_name}"))

    hpix_datasource.data = shown_hpix_data
    hover_tool = bokeh.models.HoverTool(renderers=[hpix_renderer], tooltips=tooltips)
    sky_map.plot.tools.append(hover_tool)

    return sky_map
