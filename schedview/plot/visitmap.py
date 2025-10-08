from collections import defaultdict
from datetime import datetime
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
from schedview.collect import load_bright_stars
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
    conditions_list,
    hatch=False,
    fade_scale=2.0 / (24 * 60),
    camera_perimeter="LSST",
    show_stars=False,
    map_classes=[ArmillarySphere, Planisphere],
    footprint_outline=None,
    applet_mode=False,
):
    """
    Multi-night visit plots with shared MJD slider.

    Parameters
    ----------
    visits : pd.DataFrame
        Must contain 'day_obs', 'observationStartMJD',
        'fieldRA', 'fieldDec', 'band'
    footprint : np.array or None
        Healpix footprint
    conditions_list : list
        List of nightly Conditions objects, one per night to plot
    hatch : bool
        Use hatching patterns for bands instead of solid colors
    fade_scale : float
        Time scale for fading visit markers
    camera_perimeter : str or callable
        Camera footprint perimeter function
    show_stars : bool
        Show bright stars on the map
    map_classes : list
        List of spheremap classes to instantiate
    footprint_outline : object or None
        Footprint outline polygons
    applet_mode : bool
        If True, uses compact fixed sizing for dashboard (380x220).
        If False, uses responsive full-size mode for both maps.
    """
    # Initialize spheremaps
    reference_conditions = conditions_list[0]
    spheremaps = [mc(mjd=reference_conditions.mjd) for mc in map_classes]

    if camera_perimeter == "LSST":
        camera_perimeter = LsstCameraFootprintPerimeter()

    # Configure figure sizing based on mode
    if applet_mode:
        # Applet mode: small fixed size for dashboard
        spheremaps[0].figure.width = 380
        spheremaps[0].figure.height = 220
    else:
        # Full mode: responsive sizing with matched heights
        for sm in spheremaps:
            sm.figure.sizing_mode = "stretch_width"

    # Setup shared MJD slider
    if "mjd" not in spheremaps[0].sliders:
        spheremaps[0].add_mjd_slider()

    mjd_start = min(cond.sun_n12_setting for cond in conditions_list)
    mjd_end = max(cond.sun_n12_rising for cond in conditions_list)

    mjd_slider = spheremaps[0].sliders["mjd"]
    mjd_slider.start = mjd_start
    mjd_slider.end = mjd_end
    mjd_slider.value = mjd_start

    # Share slider across all spheremaps
    for sm in spheremaps[1:]:
        sm.sliders["mjd"] = mjd_slider

    # Add footprints
    if footprint_outline is not None:
        add_footprint_outlines_to_skymaps(
            footprint_outline, spheremaps, line_width=5, colormap=defaultdict(lambda: "gray")
        )
    if footprint is not None:
        add_footprint_to_skymaps(footprint, spheremaps)

    # Add visit patches per night and band
    unique_nights = sorted(visits["day_obs"].unique())
    night_renderers = _add_visit_patches(visits, unique_nights, spheremaps, camera_perimeter, hatch)

    # Add sun, moon, stars, and horizon markers
    all_sun_markers, all_moon_markers = _add_celestial_objects(conditions_list, spheremaps, show_stars)

    # Create night label
    dayobs_label = bokeh.models.Div(text=f"Night: {unique_nights[0]}", width=150)

    # Setup JavaScript callback for slider interaction
    _setup_slider_callback(
        mjd_slider,
        night_renderers,
        all_sun_markers,
        all_moon_markers,
        dayobs_label,
        unique_nights,
        conditions_list,
        fade_scale,
    )

    # Layout based on mode
    if applet_mode:
        # Applet mode: single map with slider and label below
        # Use column layout with all controls below the map
        fig = bokeh.layouts.column(spheremaps[0].figure, mjd_slider, dayobs_label)
    else:
        # Full mode: side-by-side maps with controls below
        # Maps in a row, controls naturally appear below each map
        if len(spheremaps) == 1:
            # Single map in full mode (planisphere only)
            fig = bokeh.layouts.column(spheremaps[0].figure, mjd_slider, dayobs_label)
        else:
            # Multiple maps side by side
            # ArmillarySphere sliders will appear below its map automatically
            # We only add the shared MJD slider and label for the whole layout
            row_plots = bokeh.layouts.row([sm.figure for sm in spheremaps])
            fig = bokeh.layouts.column(row_plots, dayobs_label)

    # Decorate maps
    for sm in spheremaps:
        sm.decorate()

    return fig


def _add_visit_patches(visits, unique_nights, spheremaps, camera_perimeter, hatch):
    """Add visit patches for each night and band."""
    night_renderers = []

    for night_idx, day_obs in enumerate(unique_nights):
        night_visits = visits[visits["day_obs"] == day_obs]
        band_renderers = []

        for band in "ugrizy":
            band_visits = night_visits[night_visits[band_column(night_visits)] == band].copy()

            if band_visits.empty:
                continue

            # Calculate camera footprint positions
            ras, decls = camera_perimeter(band_visits.fieldRA, band_visits.fieldDec, band_visits.rotSkyPos)
            band_visits["ra"] = ras
            band_visits["decl"] = decls
            band_visits["mjd"] = band_visits.observationStartMJD.values
            band_visits["fill_alpha"] = [0.0] * len(band_visits)
            band_visits["line_alpha"] = [0.0] * len(band_visits)

            # Setup patch styling
            patches_kwargs = dict(
                fill_alpha="fill_alpha",
                line_alpha="line_alpha",
                fill_color=None if hatch else PLOT_BAND_COLORS[band],
                line_color="#ff00ff",
                line_width=2,
                name=f"visit_{night_idx}_{band}",
            )

            if hatch:
                patches_kwargs.update(
                    hatch_alpha="fill_alpha",
                    hatch_color=PLOT_BAND_COLORS[band],
                    hatch_pattern=BAND_HATCH_PATTERNS[band],
                    hatch_scale=BAND_HATCH_SCALES[band],
                )

            # Add patches to all spheremaps
            cds = spheremaps[0].add_patches(band_visits, patches_kwargs=patches_kwargs)
            for sm in spheremaps[1:]:
                sm.add_patches(data_source=cds, patches_kwargs=patches_kwargs)

            # Add hover tooltips
            for sm in spheremaps:
                hover = bokeh.models.HoverTool(
                    renderers=[sm.plot.select({"name": patches_kwargs["name"]})[0]],
                    tooltips=VISIT_TOOLTIPS,
                    formatters={"@start_timestamp": "datetime"},
                )
                sm.plot.add_tools(hover)

            band_renderers.append(cds)

        night_renderers.append(band_renderers)

    return night_renderers


def _add_celestial_objects(conditions_list, spheremaps, show_stars):
    """Add sun, moon, stars, and horizon to spheremaps."""
    # Convert celestial coordinates to degrees
    sun_ras_deg = [np.degrees(c.sun_ra) for c in conditions_list]
    sun_decs_deg = [np.degrees(c.sun_dec) for c in conditions_list]
    moon_ras_deg = [np.degrees(c.moon_ra) for c in conditions_list]
    moon_decs_deg = [np.degrees(c.moon_dec) for c in conditions_list]

    all_sun_markers = []
    all_moon_markers = []

    for sm_idx, sm in enumerate(spheremaps):
        sun_markers = []
        moon_markers = []

        # Add sun and moon markers for each night
        for night_idx, (sun_ra, sun_dec, moon_ra, moon_dec) in enumerate(
            zip(sun_ras_deg, sun_decs_deg, moon_ras_deg, moon_decs_deg)
        ):
            # Add sun marker
            n_renderers_before = len(sm.plot.renderers)
            sm.add_marker(
                sun_ra,
                sun_dec,
                name=f"Sun_{sm_idx}_{night_idx}",
                glyph_size=15,
                circle_kwargs={
                    "color": "yellow",
                    "fill_alpha": 1.0 if night_idx == 0 else 0.0,
                    "line_alpha": 0.0,
                },
            )
            sun_markers.append(sm.plot.renderers[n_renderers_before])

            # Add moon marker
            n_renderers_before = len(sm.plot.renderers)
            sm.add_marker(
                moon_ra,
                moon_dec,
                name=f"Moon_{sm_idx}_{night_idx}",
                glyph_size=15,
                circle_kwargs={
                    "color": "orange",
                    "fill_alpha": 0.8 if night_idx == 0 else 0.0,
                    "line_alpha": 0.0,
                },
            )
            moon_markers.append(sm.plot.renderers[n_renderers_before])

        # Add stars (once per spheremap)
        if show_stars:
            star_data = load_bright_stars()[["name", "ra", "decl", "Vmag"]]
            star_data["glyph_size"] = 15 - (15.0 / 3.5) * star_data["Vmag"]
            star_data = star_data.query("glyph_size>0")
            sm.add_stars(star_data, mag_limit_slider=False, star_kwargs={"color": "yellow"})

        # Add horizon lines
        sm.add_horizon()
        sm.add_horizon(zd=70, line_kwargs={"color": "red", "line_width": 2})

        all_sun_markers.append(sun_markers)
        all_moon_markers.append(moon_markers)

    return all_sun_markers, all_moon_markers


def _setup_slider_callback(
    mjd_slider,
    night_renderers,
    all_sun_markers,
    all_moon_markers,
    dayobs_label,
    unique_nights,
    conditions_list,
    fade_scale,
):
    """Setup JavaScript callback for MJD slider interaction."""
    callback_code = """
    const mjd_val = mjd_slider.value;
    let current_day = null;

    // Update visit patch alphas
    for (let i = 0; i < sources.length; i++) {
        const start = mjd_starts[i];
        const end = mjd_ends[i];

        if (mjd_val >= start && mjd_val <= end) {
            current_day = day_obs_list[i];
        }

        const band_sources = sources[i];
        for (let j = 0; j < band_sources.length; j++) {
            const cds = band_sources[j];
            const data = cds.data;

            for (let k = 0; k < data['mjd'].length; k++) {
                if (mjd_val >= data['mjd'][k]) {
                    data['fill_alpha'][k] = 0.5;
                    data['line_alpha'][k] = Math.max(
                        0,
                        1 - (mjd_val - data['mjd'][k]) / scale
                    );
                } else {
                    data['fill_alpha'][k] = 0.0;
                    data['line_alpha'][k] = 0.0;
                }
            }
            cds.change.emit();
        }
    }

    // Update sun and moon visibility
    if (current_day === null) {
        day_label.text = "No night";
        _hide_all_celestial_markers(all_sun_markers, all_moon_markers);
    } else {
        const idx = day_obs_list.indexOf(current_day);
        _update_celestial_markers(all_sun_markers, all_moon_markers, idx);
        day_label.text = "Night: " + current_day;
    }

    function _hide_all_celestial_markers(sun_markers, moon_markers) {
        for (let s = 0; s < sun_markers.length; s++) {
            for (let m = 0; m < sun_markers[s].length; m++) {
                sun_markers[s][m].glyph.fill_alpha = 0.0;
                moon_markers[s][m].glyph.fill_alpha = 0.0;
                sun_markers[s][m].data_source.change.emit();
                moon_markers[s][m].data_source.change.emit();
            }
        }
    }

    function _update_celestial_markers(sun_markers, moon_markers, night_idx) {
        for (let s = 0; s < sun_markers.length; s++) {
            for (let m = 0; m < sun_markers[s].length; m++) {
                if (m === night_idx) {
                    sun_markers[s][m].glyph.fill_alpha = 1.0;
                    moon_markers[s][m].glyph.fill_alpha = 0.8;
                } else {
                    sun_markers[s][m].glyph.fill_alpha = 0.0;
                    moon_markers[s][m].glyph.fill_alpha = 0.0;
                }
                sun_markers[s][m].data_source.change.emit();
                moon_markers[s][m].data_source.change.emit();
            }
        }
    }
    """

    mjd_slider.js_on_change(
        "value",
        bokeh.models.CustomJS(
            args=dict(
                mjd_slider=mjd_slider,
                sources=night_renderers,
                day_label=dayobs_label,
                day_obs_list=unique_nights,
                mjd_starts=[cond.sun_n12_setting for cond in conditions_list],
                mjd_ends=[cond.sun_n12_rising for cond in conditions_list],
                scale=fade_scale,
                all_sun_markers=all_sun_markers,
                all_moon_markers=all_moon_markers,
            ),
            code=callback_code,
        ),
    )


def create_visit_skymaps(
    visits,
    nside=32,
    observatory=None,
    timezone="Chile/Continental",
    planisphere_only=False,
    applet_mode=False,
):
    """
    Prepare data for multi-night SphereMap plotting.
    Returns figure and data dict.
    """

    # Prepare observatory and conditions per night
    if observatory is None:
        observatory = ModelObservatory(nside=nside, init_load_length=1)
        observatory.sky_model.load_length = 1

    unique_nights = sorted(visits["day_obs"].unique())

    conditions_list = []
    for day_obs in unique_nights:
        night_date = datetime.strptime(str(day_obs), "%Y%m%d").date()
        night_events = schedview.compute.astro.night_events(
            night_date=night_date, site=observatory.location, timezone=timezone
        )
        # start_time = Time(night_events.loc["sunset","UTC"])
        end_time = Time(night_events.loc["sunrise", "UTC"])
        observatory.mjd = end_time.mjd
        conditions_list.append(observatory.return_conditions())

    # Footprint outline
    footprint_regions = get_current_footprint(nside)[1]
    footprint_regions[np.isin(footprint_regions, ["bulgy", "lowdust"])] = "WFD"
    footprint_regions[
        np.isin(footprint_regions, ["LMC_SMC", "dusty_plane", "euclid_overlap", "nes", "scp", "virgo"])
    ] = "other"
    footprint_outline = find_healpix_area_polygons(footprint_regions)
    tiny_loops = footprint_outline.groupby(["region", "loop"]).count().query("RA<10").index
    footprint_outline = footprint_outline.drop(tiny_loops)

    data = {
        "visits": visits,
        "footprint": None,
        "footprint_outline": footprint_outline,
        "conditions_list": conditions_list,
        "applet_mode": applet_mode,
    }

    # Call plotting function
    if applet_mode or planisphere_only:
        vmap = plot_visit_skymaps(map_classes=[Planisphere], **data)
    else:
        vmap = plot_visit_skymaps(map_classes=[ArmillarySphere, Planisphere], **data)

    return vmap, data


def plot_visit_planisphere(*args, **kwargs):
    warn("Use plot_visit_skymaps and set map_classes instead", category=DeprecationWarning)
    kwargs["map_classes"] = [Planisphere]
    return plot_visit_skymaps(*args, **kwargs)
