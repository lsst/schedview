import datetime
import re
from functools import partial

import astropy
import bokeh
import bokeh.io
import colorcet
import healpy as hp
import numpy as np
import pandas as pd
import rubin_scheduler.scheduler.features
import rubin_scheduler.scheduler.surveys  # noqa: F401
from astropy.time import Time
from bokeh.models.ui.ui_element import UIElement
from matplotlib.figure import Figure
from uranography.api import HorizonMap, Planisphere, make_zscale_linear_cmap

import schedview.compute.astro
from schedview import band_column
from schedview.compute.camera import LsstCameraFootprintPerimeter
from schedview.compute.maf import compute_hpix_metric_in_bands


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
    conditions : `rubin_scheduler.scheduler.features.Conditions`, optional
        Default is None.
        The observing conditions at which to map the survey, used to determine
        telescope pointing. If None, do not mark telescope pointing.
    survey : `rubin_scheduler.scheduler.surveys.BaseSurvey`, optional
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

    sky_map.add_horizon_graticules()

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

        sky_map.add_horizon(
            89.99, line_kwargs={"color": "#000000", "line_width": 2, "legend_label": "Horizon"}
        )
        sky_map.add_horizon(
            70, line_kwargs={"color": "#D55E00", "line_width": 2, "legend_label": "ZD = 70 degrees"}
        )

    # "line_dash": "dashed"
    sky_map.add_ecliptic(legend_label="Ecliptic", line_width=2, color="#009E73", line_dash="dashed")
    sky_map.add_galactic_plane(
        legend_label="Galactic plane", color="#0072B2", line_width=2, line_dash="dotted"
    )

    sky_map.add_marker(
        sun_coords.ra.deg,
        sun_coords.dec.deg,
        name="Sun",
        glyph_size=15,
        circle_kwargs={
            "color": "brown",
            "legend_label": "Sun position",
        },
    )
    sky_map.add_marker(
        moon_coords.ra.deg,
        moon_coords.dec.deg,
        name="Moon",
        glyph_size=15,
        circle_kwargs={
            "color": "orange",
            "legend_label": "Moon position",
            "tags": ["circle", "orange"],
        },
    )

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
            circle_kwargs={"color": "green", "fill_alpha": 0.5, "legend_label": "Telescope pointing"},
        )

    if survey is not None:
        try:
            try:
                ra_deg = list(survey.ra_deg)
                dec_deg = list(survey.dec_deg)
            except TypeError:
                ra_deg = [survey.ra_deg]
                dec_deg = [survey.dec_deg]

            survey_field_data_source = bokeh.models.ColumnDataSource(
                data={
                    "ra": ra_deg,
                    "decl": dec_deg,
                    "name": ["survey_pointing {i}" for i, ra in enumerate(ra_deg)],
                    "glyph_size": [20] * len(ra_deg),
                },
                name="survey_pointings",
            )
            sky_map.add_marker(
                data_source=survey_field_data_source,
                name="survey_field_marker",
                circle_kwargs={"color": "black", "fill_alpha": 0, "legend_label": "Survey field(s)"},
            )
        except AttributeError:
            pass

    for key in hpix_data:
        column_name = key.replace(" ", "_").replace(".", "_").replace("@", "_")
        shown_hpix_data[column_name] = hpix_data[key][shown_hpids]
        label = re.sub(" @[0-9]*$", "", key)
        tooltips.append((label, f"@{column_name}"))

    hpix_datasource.data = shown_hpix_data
    hover_tool = bokeh.models.HoverTool(renderers=[hpix_renderer], tooltips=tooltips)
    sky_map.plot.tools.append(hover_tool)

    return sky_map


def map_visits_over_hpix(
    visits,
    conditions,
    map_hpix,
    plot=None,
    scale_limits=None,
    palette=colorcet.blues,
    map_class=Planisphere,
    prerender_hpix=True,
):
    """Plot visit locations over a healpix map.

    Parameters
    ----------
    visits : `pd.DataFrame`
        The table of visits to plot, with columns matching the opsim database
        definitions.
    conditions : `rubin_scheduler.scheduler.features.Conditions`
        An instance of a rubin_scheduler conditions object.
    map_hpix : `numpy.array`
        An array of healpix values
    plot : `bokeh.models.plots.Plot` or `None`
        The bokeh plot on which to make the plot. None creates a new plot.
        None by default.
    scale_limits : `list` of `float` or `None`
        The scale limits for the healpix values. If None, use zscale to set
        the scale.
    palette : `str`
        The bokeh palette to use for the healpix map.
    map_class : `class`, optional
        The class of map to use.  Defaults to uranography.Planisphere.
    prerender_hpix : `bool`, optional
        Pre-render the healpix map? Defaults to True

    Returns
    -------
    plot : `bokeh.models.plots.Plot`
        The plot with the map
    """
    camera_perimeter = LsstCameraFootprintPerimeter()

    if plot is None:
        plot = bokeh.plotting.figure(frame_width=256, frame_height=256, match_aspect=True)

    sphere_map = map_class(mjd=conditions.mjd, plot=plot)

    if scale_limits is None:
        try:
            good_values = map_hpix[~map_hpix.mask]
        except AttributeError:
            good_values = map_hpix

        cmap = make_zscale_linear_cmap(good_values, palette=palette)
    else:
        cmap = bokeh.transform.linear_cmap("value", palette, scale_limits[0], scale_limits[1])

    if prerender_hpix:
        # Convert the healpix map into an image raster, and send that instead
        # the full healpix map (sent as one polygon for each healpixel).
        # An high nside, this should reduce the data sent to the browser.
        # However, it will not be responsive to controls.
        if not map_class == Planisphere:
            raise NotImplementedError()
        if not plot.frame_width == plot.frame_height:
            raise NotImplementedError()

        xsize = plot.frame_width
        ysize = plot.frame_height
        # For Lambert Azimuthal Equal Area, projection space is 4 radians wide
        # and high, so projection units per pixel is 4 radians/xsize.
        # reso is in units of arcmin, though.
        reso = 60 * np.degrees(4.0 / xsize)
        projector = hp.projector.AzimuthalProj(
            rot=sphere_map.laea_rot, xsize=xsize, ysize=ysize, reso=reso, lamb=True
        )
        map_raster = projector.projmap(map_hpix, partial(hp.vec2pix, hp.npix2nside(len(map_hpix))))

        # Set area outside projection to nan, not -inf, so bokeh does not
        # try coloring it.
        map_raster[np.isneginf(map_raster)] = np.nan

        reso_radians = np.radians(projector.arrayinfo["reso"] / 60)
        width_hpxy = reso_radians * map_raster.shape[0]
        height_hpxy = reso_radians * map_raster.shape[1]
        sphere_map.plot.image(
            [map_raster],
            x=-width_hpxy / 2,
            y=-height_hpxy / 2,
            dw=width_hpxy,
            dh=height_hpxy,
            color_mapper=cmap.transform,
            level="image",
        )
    else:
        sphere_map.add_healpix(map_hpix, nside=hp.npix2nside(len(map_hpix)), cmap=cmap)

    if len(visits) > 0:
        ras, decls = camera_perimeter(visits.fieldRA, visits.fieldDec, visits.rotSkyPos)

        perimeter_df = pd.DataFrame(
            {
                "ra": ras,
                "decl": decls,
            }
        )
        sphere_map.add_patches(
            perimeter_df, patches_kwargs={"fill_color": None, "line_color": "black", "line_width": 1}
        )

    sphere_map.decorate()

    sphere_map.add_marker(
        ra=np.degrees(conditions.sun_ra),
        decl=np.degrees(conditions.sun_dec),
        name="Sun",
        glyph_size=8,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )

    sphere_map.add_marker(
        ra=np.degrees(conditions.moon_ra),
        decl=np.degrees(conditions.moon_dec),
        name="Moon",
        glyph_size=8,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )

    return plot


def create_hpix_visit_map_grid(hpix_maps, visits, conditions, **kwargs):
    """Create a grid of healpix maps with visits overplotted.

    Notes
    -----
    Additional keyword args are passed to map_visits_over_hpix.

    Parameters
    ----------
    map_hpix : `numpy.array`
        An array of healpix values
    visits : `pd.DataFrame`
        The table of visits to plot, with columns matching the opsim database
        definitions.
    conditions : `rubin_scheduler.scheduler.features.Conditions`
        An instance of a rubin_scheduler conditions object.

    Returns
    -------
    plot : `bokeh.models.plots.Plot`
        The plot with the map
    """
    visit_map = {}
    for band in hpix_maps:
        visit_map[band] = map_visits_over_hpix(
            visits.query(f"filter == '{band}'"), conditions, hpix_maps[band], **kwargs
        )
        visit_map[band].title = band

    # Convert the dictionary of maps into a list of lists,
    # corresponding to the rows of the grid.
    num_cols = 3
    map_lists = []
    for band_idx, band in enumerate(hpix_maps):
        if band_idx % num_cols == 0:
            map_lists.append([visit_map[band]])
        else:
            map_lists[-1].append(visit_map[band])

    map_grid = bokeh.layouts.gridplot(map_lists)
    return map_grid


def create_metric_visit_map_grid(
    metric, metric_visits, visits, observatory, nside=32, use_matplotlib=False, **kwargs
) -> Figure | UIElement | None:
    """Create a grid of maps of metric values with visits overplotted.

    Parameters
    ----------
    metric : `numpy.array`
        An array of healpix values
    metric_visits : `pd.DataFrame`
        The visits to use to compute the metric
    visits : `pd.DataFrame`
        The table of visits to plot, with columns matching the opsim database
        definitions.
    observatory : `ModelObservatory`
        The model observotary to use.
    nside : `int`
        The nside with which to compute the metric.
    use_matplotlib: `bool`
        Use matplotlib instead of bokeh? Defaults to False.

    Returns
    -------
    plot : `bokeh.models.plots.Plot`
        The plot with the map
    """

    if len(metric_visits):
        metric_hpix = compute_hpix_metric_in_bands(metric_visits, metric, nside=nside)
    else:
        metric_hpix = {b: np.zeros(hp.nside2npix(nside)) for b in visits[band_column(visits)].unique()}

    if len(visits):
        if use_matplotlib:
            from schedview.plot import survey_skyproj

            day_obs_mjd = np.floor(observatory.mjd - 0.5).astype("int")
            day_obs_dt = Time(day_obs_mjd, format="mjd").datetime
            day_obs_date = datetime.date(day_obs_dt.year, day_obs_dt.month, day_obs_dt.day)
            night_events = schedview.compute.astro.night_events(day_obs_date)
            fig = survey_skyproj.create_hpix_visit_map_grid(
                visits, metric_hpix, observatory, night_events, **kwargs
            )
            return fig
        else:
            map_grid = create_hpix_visit_map_grid(
                metric_hpix, visits, observatory.return_conditions(), **kwargs
            )
            bokeh.io.show(map_grid)
            return map_grid
    else:
        print("No visits")

    return None
