from warnings import warn

import bokeh
import healpy as hp
import numpy as np
from astropy.time import Time

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory
from rubin_scheduler.scheduler.schedulers import CoreScheduler  # noqa F401
from uranography.api import ArmillarySphere, Planisphere, split_healpix_by_resolution

import schedview.collect.scheduler_pickle
import schedview.compute.astro
from schedview.collect.stars import load_bright_stars
from schedview.compute.camera import LsstCameraFootprintPerimeter

BAND_COLORS = dict(u="#56b4e9", g="#008060", r="#ff4000", i="#850000", z="#6600cc", y="#222222")
BAND_HATCH_PATTERNS = dict(
    u="dot",
    g="ring",
    r="horizontal_line",
    i="vertical_line",
    z="right_diagonal_line",
    y="left_diagonal_line",
)
BAND_HATCH_SCALES = dict(u=6, g=6, r=6, i=6, z=12, y=12)
VISIT_TOOLTIPS = (
    "@observationId: @start_date{%F %T} UTC (mjd=@observationStartMJD{00000.0000}, "
    + "LST=@observationStartLST\u00b0), band=@filter, RA=@fieldRA\u00b0, Decl=@fieldDec\u00b0, "
    + "PA=@paraAngle\u00b0, Az=@azimuth\u00b0, Alt=@altitude\u00b0, @note"
)
VISIT_COLUMNS = [
    "observationId",
    "start_date",
    "observationStartMJD",
    "observationStartLST",
    "filter",
    "fieldRA",
    "fieldDec",
    "rotSkyPos",
    "paraAngle",
    "azimuth",
    "altitude",
    "note",
]

NSIDE_LOW = 8


def plot_visit_skymaps(
    visits,
    footprint,
    conditions,
    hatch=False,
    fade_scale=2.0 / (24 * 60),
    camera_perimeter="LSST",
    nside_low=8,
    show_stars=False,
    map_classes=[ArmillarySphere, Planisphere],
):
    """Plot visits on a map of the sky.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        One row per visit, with at least the following columns:

        ``"fieldRA"``
            The visit R.A. in degrees (`float`).
        ``"fieldDec"``
            The visit declination in degrees (`float`).
        ``"observationStartMJD"``
            The visit start MJD (`float`).
        ``"filter"``
            The visit filter (`str`)

    footprint : `numpy.array`
        A healpix map of the footprint.
    conditions : `rubin_scheduler.scheduler.features.conditions.Conditions`
        The conditions for the night, which determines the start and end
        times covered by the map.
    hatch : `bool`
        Use hatches instead of filling visit polygons. (SLOW!)
    fade_scale : `float`
        Time (in days) over which visit outlines fade.
    camera_perimeter : `str` or `object`
        An function that returns the perimeter of the camera footprint,
        or "LSST" for the LSST camera footprint.
        Defaults to "LSST".
    nside_low : `int`
        The healpix nside to try to use for low resolution sections of the
        healpix map.
    show_stars : `bool`
        Show stars? (Defaults to False)

    Returns
    -------
    _type_
        _description_
    """

    if camera_perimeter == "LSST":
        camera_perimeter = LsstCameraFootprintPerimeter()

    nside_low = NSIDE_LOW

    spheremaps = [mc(mjd=conditions.mjd) for mc in map_classes]

    # Add an MJD slider to the reference (first) projection
    if "mjd" not in spheremaps[0].sliders:
        spheremaps[0].add_mjd_slider()

    spheremaps[0].sliders["mjd"].start = conditions.sun_n12_setting
    spheremaps[0].sliders["mjd"].end = conditions.sun_n12_rising

    for spheremap in spheremaps[1:]:
        spheremap.sliders["mjd"] = spheremaps[0].sliders["mjd"]

    cmap = bokeh.transform.linear_cmap("value", "Greys256", int(np.ceil(np.nanmax(footprint) * 2)), 0)

    nside_high = hp.npix2nside(footprint.shape[0])
    footprint_high, footprint_low = split_healpix_by_resolution(footprint, nside_low, nside_high)

    healpix_high_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_high, nside=nside_high, cmap=cmap)
    healpix_low_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_low, nside=nside_low, cmap=cmap)

    for spheremap in spheremaps[1:]:
        spheremap.add_healpix(healpix_high_ds, nside=nside_high, cmap=cmap)
        spheremap.add_healpix(healpix_low_ds, nside=nside_low, cmap=cmap)

    # Transforms for recent, past, future visits
    past_future_js = """
        const result = new Array(xs.length)
        for (let i = 0; i < xs.length; i++) {
        if (mjd_slider.value >= xs[i]) {
            result[i] = past_value
        } else {
            result[i] = future_value
        }
        }
        return result
    """

    past_future_transform = bokeh.models.CustomJSTransform(
        args=dict(mjd_slider=spheremaps[0].sliders["mjd"], past_value=0.5, future_value=0.0),
        v_func=past_future_js,
    )

    recent_js = """
        const result = new Array(xs.length)
        for (let i = 0; i < xs.length; i++) {
        if (mjd_slider.value < xs[i]) {
            result[i] = 0
        } else {
            result[i] = Math.max(0, max_value * (1 - (mjd_slider.value - xs[i]) / scale))
        }
        }
        return result
    """

    recent_transform = bokeh.models.CustomJSTransform(
        args=dict(mjd_slider=spheremaps[0].sliders["mjd"], max_value=1.0, scale=fade_scale),
        v_func=recent_js,
    )

    for band in "ugrizy":
        band_visits = visits.reset_index().loc[visits["filter"] == band, VISIT_COLUMNS].copy()

        if len(band_visits) < 1:
            continue

        ras, decls = camera_perimeter(band_visits.fieldRA, band_visits.fieldDec, band_visits.rotSkyPos)
        band_visits = band_visits.assign(ra=ras, decl=decls, mjd=band_visits.observationStartMJD.values)

        patches_kwargs = dict(
            fill_alpha=bokeh.transform.transform("mjd", past_future_transform),
            line_alpha=bokeh.transform.transform("mjd", recent_transform),
            line_color="#ff00ff",
            line_width=2,
            name="visit_patches",
        )

        if hatch:
            patches_kwargs.update(
                dict(
                    fill_alpha=0,
                    fill_color=None,
                    hatch_alpha=bokeh.transform.transform("mjd", past_future_transform),
                    hatch_color=BAND_COLORS[band],
                    hatch_pattern=BAND_HATCH_PATTERNS[band],
                    hatch_scale=BAND_HATCH_SCALES[band],
                )
            )
        else:
            patches_kwargs.update(dict(fill_color=BAND_COLORS[band]))

        visit_ds = spheremaps[0].add_patches(
            band_visits,
            patches_kwargs=patches_kwargs,
        )

        for spheremap in spheremaps[1:]:
            spheremap.add_patches(data_source=visit_ds, patches_kwargs=patches_kwargs)

        # Add hovertools
        for spheremap in spheremaps:
            plot = spheremap.plot
            hover_tool = bokeh.models.HoverTool()
            hover_tool.renderers = list(plot.select({"name": "visit_patches"}))
            hover_tool.tooltips = VISIT_TOOLTIPS
            hover_tool.formatters = {"@start_date": "datetime"}
            plot.add_tools(hover_tool)

    for spheremap in spheremaps:
        spheremap.decorate()

    spheremap = spheremaps[0]
    sun_ds = spheremap.add_marker(
        ra=np.degrees(conditions.sun_ra),
        decl=np.degrees(conditions.sun_dec),
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )

    moon_ds = spheremap.add_marker(
        ra=np.degrees(conditions.moon_ra),
        decl=np.degrees(conditions.moon_dec),
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )

    if show_stars:
        star_data = load_bright_stars().loc[:, ["name", "ra", "decl", "Vmag"]]
        star_data["glyph_size"] = 15 - (15.0 / 3.5) * star_data["Vmag"]
        star_data.query("glyph_size>0", inplace=True)
        star_ds = spheremaps[0].add_stars(star_data, mag_limit_slider=False, star_kwargs={"color": "yellow"})

    horizon_ds = spheremap.add_horizon()
    horizon70_ds = spheremap.add_horizon(zd=70, line_kwargs={"color": "red", "line_width": 2})

    for spheremap in spheremaps[1:]:
        spheremap.add_marker(
            data_source=sun_ds,
            name="Sun",
            glyph_size=15,
            circle_kwargs={"color": "yellow", "fill_alpha": 1},
        )

        spheremap.add_marker(
            data_source=moon_ds,
            name="Moon",
            glyph_size=15,
            circle_kwargs={"color": "orange", "fill_alpha": 0.8},
        )

        spheremap.add_horizon(data_source=horizon_ds)
        spheremap.add_horizon(data_source=horizon70_ds, line_kwargs={"color": "red", "line_width": 2})

        if show_stars:
            for spheremap in spheremaps[1:]:
                spheremap.add_stars(
                    star_data,
                    data_source=star_ds,
                    mag_limit_slider=True,
                    star_kwargs={"color": "yellow"},
                )

    fig = bokeh.layouts.row(list(s.figure for s in spheremaps))
    return fig


def plot_visit_planisphere(*args, **kwargs):
    warn("Use plot_visit_skymaps and set map_classes instead", category=DeprecationWarning)
    kwargs["map_classes"] = [Planisphere]
    return plot_visit_skymaps(*args, **kwargs)


def create_visit_skymaps(
    visits,
    night_date,
    nside=32,
    observatory=None,
    timezone="Chile/Continental",
    planisphere_only=False,
):
    """Create a map of visits on the sky.

    Parameters
    ----------
    visits : `pandas.DataFrame` or `str`
        If a `pandas.DataFrame`, it needs at least the following columns:

        ``"fieldRA"``
            The visit R.A. in degrees (`float`).
        ``"fieldDec"``
            The visit declination in degrees (`float`).
        ``"observationStartMJD"``
            The visit start MJD (`float`).
        ``"filter"``
            The visit filter (`str`)

        If a string, the file name of the opsim database from which the
        visits should be loaded.
    night_date : `datetime.date`
        The calendar date of the evening of the night for which
        to plot the visits.
    nside : `int`, optional
        The healpix nside to use for the map.
    observatory : `ModelObservatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None.
    timezone : `str`, optional
        by default "Chile/Continental"
    planisphere_only : `bool`
        by default False

    Returns
    -------
    figure : `bokeh.models.layouts.LayoutDOM`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_visit_skymaps`.
    """
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(night_date=night_date, site=site, timezone=timezone)
    start_time = Time(night_events.loc["sunset", "UTC"])
    end_time = Time(night_events.loc["sunrise", "UTC"])

    if isinstance(visits, str):
        visits = schedview.collect.opsim.read_opsim(visits)

    if start_time is not None:
        visits.query(f"observationStartMJD >= {Time(start_time).mjd}", inplace=True)

    if end_time is not None:
        visits.query(f"observationStartMJD <= {Time(end_time).mjd}", inplace=True)

    if observatory is None:
        observatory = ModelObservatory(nside=nside, init_load_length=1)
        observatory.sky_model.load_length = 1

    footprint = schedview.collect.footprint.get_footprint(nside)
    observatory.mjd = end_time.mjd
    conditions = observatory.return_conditions()
    data = {"visits": visits, "footprint": footprint, "conditions": conditions}
    if planisphere_only:
        vmap = schedview.plot.visitmap.plot_visit_skymaps(map_classes=[Planisphere], **data)
    else:
        vmap = schedview.plot.visitmap.plot_visit_skymaps(**data)

    return vmap, data
