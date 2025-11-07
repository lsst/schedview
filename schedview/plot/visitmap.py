from collections import defaultdict
from warnings import warn

import bokeh
import numpy as np
from astropy.time import Time
from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory
from rubin_scheduler.scheduler.schedulers import CoreScheduler  # noqa F401

# Imported to help sphinx make the link
from rubin_scheduler.scheduler.utils import get_current_footprint
from uranography.api import ArmillarySphere, Planisphere

import schedview.compute.astro
from schedview import band_column
from schedview.collect import load_bright_stars, read_opsim
from schedview.compute.camera import LsstCameraFootprintPerimeter
from schedview.compute.footprint import find_healpix_area_polygons
from schedview.plot import PLOT_BAND_COLORS

from .footprint import add_footprint_outlines_to_skymaps, add_footprint_to_skymaps

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
    "@observationId: @start_timestamp{%F %T} UTC (mjd=@observationStartMJD{00000.0000}, "
    + "LST=@observationStartLST\u00b0): "
    + "@observation_reason (@science_program), "
    + "in @band at \u03b1,\u03b4=@fieldRA\u00b0,@fieldDec\u00b0; "
    + "q=@paraAngle\u00b0; a,A=@azimuth\u00b0,@altitude\u00b0"
)


VISIT_COLUMNS = [
    "observationId",
    "start_timestamp",
    "observationStartMJD",
    "observationStartLST",
    "band",
    "fieldRA",
    "fieldDec",
    "rotSkyPos",
    "paraAngle",
    "azimuth",
    "altitude",
    "observation_reason",
    "science_program",
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
    footprint_outline=None,
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
        ``"band"``
            The visit band (`str`)

    footprint : `numpy.array` or `None`
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
    footprint_outline : `bool` or `None`
        Outline the footprint instead of filling it in (much faster to render).
        Defaults to True.

    Returns
    -------
    fig : `bokeh.models.layouts.LayoutDOM`
        A bokeh element that can be displayed, or incorporated into a larger
        element.
    """

    if camera_perimeter == "LSST":
        camera_perimeter = LsstCameraFootprintPerimeter()

    spheremaps = [mc(mjd=conditions.mjd) for mc in map_classes]

    # Add an MJD slider to the reference (first) projection
    if "mjd" not in spheremaps[0].sliders:
        spheremaps[0].add_mjd_slider()

    spheremaps[0].sliders["mjd"].start = conditions.sun_n12_setting
    spheremaps[0].sliders["mjd"].end = conditions.sun_n12_rising

    for spheremap in spheremaps[1:]:
        spheremap.sliders["mjd"] = spheremaps[0].sliders["mjd"]

    if footprint_outline is not None:
        add_footprint_outlines_to_skymaps(
            footprint_outline, spheremaps, line_width=5, colormap=defaultdict(np.array(["gray"]).item)
        )

    if footprint is not None:
        add_footprint_to_skymaps(footprint, spheremaps)

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
        visit_columns = [
            "filter" if (c == "band" and "band" not in visits.columns) else c for c in VISIT_COLUMNS
        ]

        band_visits = (
            visits.reset_index().loc[visits.reset_index()[band_column(visits)] == band, visit_columns].copy()
        )

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
                    hatch_alpha=bokeh.transform.transform("mjd", past_future_transform),
                    hatch_color=PLOT_BAND_COLORS[band],
                    hatch_pattern=BAND_HATCH_PATTERNS[band],
                    hatch_scale=BAND_HATCH_SCALES[band],
                )
            )
        else:
            patches_kwargs.update(dict(fill_color=PLOT_BAND_COLORS[band]))

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
            hover_tool.formatters = {"@start_timestamp": "datetime"}
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
        ``"band"``
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
        visits = read_opsim(visits)

    if start_time is not None:
        visits = visits.query(f"observationStartMJD >= {Time(start_time).mjd}")

    if end_time is not None:
        visits = visits.query(f"observationStartMJD <= {Time(end_time).mjd}")

    if observatory is None:
        observatory = ModelObservatory(nside=nside, no_sky=True)

    footprint_regions = get_current_footprint(nside)[1]
    footprint_regions[np.isin(footprint_regions, ["bulgy", "lowdust"])] = "WFD"
    footprint_regions[
        np.isin(footprint_regions, ["LMC_SMC", "dusty_plane", "euclid_overlap", "nes", "scp", "virgo"])
    ] = "other"

    # Get rid of tine little loops
    footprint_outline = find_healpix_area_polygons(footprint_regions)
    tiny_loops = footprint_outline.groupby(["region", "loop"]).count().query("RA<10").index
    footprint_outline = footprint_outline.drop(tiny_loops)

    observatory.mjd = end_time.mjd
    conditions = observatory.return_conditions()
    data = {
        "visits": visits,
        "footprint": None,
        "footprint_outline": footprint_outline,
        "conditions": conditions,
    }
    if planisphere_only:
        vmap = schedview.plot.visitmap.plot_visit_skymaps(map_classes=[Planisphere], **data)
    else:
        vmap = schedview.plot.visitmap.plot_visit_skymaps(**data)

    return vmap, data
