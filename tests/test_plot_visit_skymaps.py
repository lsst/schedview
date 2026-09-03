"""Unit tests for schedview.plot.visit_skymaps module."""

import pathlib
import tempfile

import bokeh.io
import bokeh.models
import healpy as hp
import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import get_current_footprint
from uranography.api import ArmillarySphere, Planisphere

from schedview.plot.visit_skymaps import VisitMapBuilder

TEST_VISITS = pd.DataFrame(
    {
        "fieldRA": [59.780536346361515, 62.84973607079297],
        "fieldDec": [-49.19329541107385, -47.84742038715563],
        "observationStartMJD": [61105.09302481122, 61105.09346446205],
        "band": ["i", "i"],
        "rotSkyPos": [46.55499643418069, 41.58312568172861],
        "observationId": [2026030500054, 2026030500055],
        "start_timestamp": pd.to_datetime(["2026-03-06T02:13:57Z", "2026-03-06T02:14:35Z"]),
        "observationStartLST": [126.57549341396043, 126.73420103825885],
        "paraAngle": [95.01157303654843, 94.0006966560346],
        "azimuth": [228.99332822379625, 230.8847273192659],
        "altitude": [37.30089164250424, 39.122240613722006],
        "observation_reason": ["ddf_edfs_a", "ddf_edfs_b"],
        "science_program": ["BLOCK-407", "BLOCK-407"],
    }
)

TEST_ALT_VISITS = pd.DataFrame(
    {
        "fieldRA": [29.155717698495256, 28.196457586307357],
        "fieldDec": [-21.68100073471875, -18.68709611868367],
        "observationStartMJD": [61105.0041463103, 61105.00439657373],
        "band": ["z", "z"],
        "rotSkyPos": [78.04543083088815, 79.83485071859705],
        "observationId": [0, 1],
        "start_timestamp": pd.to_datetime(["2026-03-06T00:05:58Z", "2026-03-06T00:06:19Z"]),
        "observationStartLST": [94.4899896086903, 94.58033111527438],
        "paraAngle": [113.09872516602272, 114.84576306113031],
        "azimuth": [261.99025952876906, 264.70873478710547],
        "altitude": [31.76771615131967, 29.65491863783054],
        "observation_reason": ["twilight_near_sun", "twilight_near_sun"],
        "science_program": ["BLOCK-421", "BLOCK-421"],
        "sim_index": [1, 1],
        "label": ["Sim 1 Label", "Sim 1 Label"],
    }
)

FOOTPRINT_NSIDE = 16

# Tracing outlines is slow, so use a coarse map for the outline tests.
OUTLINE_TEST_NSIDE = 4


def _make_outline_test_footprint() -> np.ndarray:
    """
    Build a small footprint map holding a region of each kind handled by
    ``VisitMapBuilder._compute_footprint_outlines``.

    Returns
    -------
    footprint: np.ndarray
        A HEALPix map of region names, with a "lowdust" band (grouped into
        "WFD"), an "nes" band (grouped into "other"), and one isolated
        "virgo" pixel, whose outline is too small to keep.
    """
    npix = hp.nside2npix(OUTLINE_TEST_NSIDE)
    decl = hp.pix2ang(OUTLINE_TEST_NSIDE, np.arange(npix), lonlat=True)[1]
    footprint = np.full(npix, "", dtype="<U20")
    footprint[(decl > -40) & (decl < -20)] = "lowdust"
    footprint[(decl > 10) & (decl < 30)] = "nes"
    footprint[0] = "virgo"
    return footprint


def _select_footprint_outline_renderers(viewable: bokeh.models.UIElement) -> list:
    """
    Collect the footprint outline renderers in a built viewable.

    Parameters
    ----------
    viewable: bokeh.models.UIElement
        The Bokeh object returned by ``VisitMapBuilder.build()``.

    Returns
    -------
    outline_renderers: list
        The renderers drawing footprint outlines.
    """
    # Bokeh does not support pattern matching in selection by name,
    # so iterate over all renderers and check their names explicitly.
    outline_renderers = []
    for renderer in viewable.select({"type": bokeh.models.GlyphRenderer}):
        assert isinstance(renderer.name, str)
        if renderer.name.startswith("footprint_outline"):
            outline_renderers.append(renderer)

    return outline_renderers


def _save_and_check_viewable_html(
    viewable: bokeh.models.UIElement, filename: str = "visit_skymap.html"
) -> None:
    """
    Save a Bokeh viewable to a temporary HTML file and assert that the file
    was written and has non-zero size.

    Parameters
    ----------
    viewable: bokeh.models.UIElement
        The Bokeh object returned by ``VisitMapBuilder.build()``.
    filename: str, optional
        Name of the file inside the temporary directory (default
        ``"visit_skymap.html"``).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        out_file = pathlib.Path(temp_dir) / filename
        bokeh.io.save(viewable, filename=str(out_file))
        assert out_file.is_file()
        assert out_file.stat().st_size > 0


def test_basic_build():
    """Test that the most basic builder builds."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    viewable = builder.build()

    assert isinstance(viewable, bokeh.models.UIElement)

    visit_patches = viewable.select({"name": "visit_patches"})
    assert len(list(visit_patches)) > 0

    _save_and_check_viewable_html(viewable)


def test_elaborate_build():
    """Test a builder with many chained options"""
    visits = TEST_VISITS
    footprint_regions = get_current_footprint(FOOTPRINT_NSIDE)[1]
    builder = (
        VisitMapBuilder(
            visits, mjd=visits["observationStartMJD"].max(), map_classes=[ArmillarySphere, Planisphere]
        )
        .add_visit_patches()
        .add_graticules()
        .add_ecliptic()
        .add_galactic_plane()
        ._add_mjd_slider(start=visits["observationStartMJD"].min(), end=visits["observationStartMJD"].max())
        .add_datetime_slider()
        .hide_future_visits()
        .highlight_recent_visits()
        .add_footprint_outlines(footprint_regions)
        .add_body("sun", size=15, color="yellow", alpha=1.0)
        .add_body("moon", size=15, color="orange", alpha=0.8)
        .add_horizon()
        .add_horizon(zd=70, color="red")
        .add_eq_sliders()
        .hide_horizon_sliders()
        .make_up_north()
        .show_up_selector()
    )
    viewable = builder.build()
    assert isinstance(viewable, bokeh.models.UIElement)
    _save_and_check_viewable_html(viewable)


def test_add_graticules():
    """Test that add_graticules adds graticule renderers."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    builder.add_graticules()
    viewable = builder.build()

    graticule_glyphs = viewable.select({"name": "graticule_glyph"})
    assert len(list(graticule_glyphs)) > 0

    _save_and_check_viewable_html(viewable)


def test_add_ecliptic():
    """Test that add_ecliptic adds ecliptic renderers."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_ecliptic()
    viewable = builder.build()

    ecliptic_glyphs = viewable.select({"name": "ecliptic_glyph"})
    assert len(list(ecliptic_glyphs)) > 0

    _save_and_check_viewable_html(viewable)


def test_add_body_sun():
    """Test that add_body adds a sun marker."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_body("sun", size=10, color="yellow", alpha=1.0)
    viewable = builder.build()

    sun_renderers = viewable.select({"name": "sun"})
    assert len(list(sun_renderers)) > 0

    _save_and_check_viewable_html(viewable)


def test_add_horizon():
    """Test that add_horizon adds a horizon line."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_horizon()
    viewable = builder.build()

    horizon_glyphs = viewable.select({"name": "horizon_glyph"})
    assert len(list(horizon_glyphs)) > 0

    _save_and_check_viewable_html(viewable)


def test_add_mjd_slider():
    """Test that add_mjd_slider initialises the mjd_slider attribute."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder._add_mjd_slider()
    viewable = builder.build()

    assert isinstance(builder.mjd_slider, bokeh.models.Slider)

    _save_and_check_viewable_html(viewable)


def test_hide_future_visits():
    """Test that hide_future_visits applies a transform to visit patches."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    builder.hide_future_visits()
    viewable = builder.build()

    visit_renderers = viewable.select({"name": "visit_patches"})
    assert len(list(visit_renderers)) > 0
    # TODO look for callback

    _save_and_check_viewable_html(viewable)


def test_highlight_recent_visits():
    """Test that highlight_recent_visits applies its transform."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    builder.highlight_recent_visits()
    viewable = builder.build()

    # Check that a transform was applied to the visit patches
    visit_renderers = viewable.select({"name": "visit_patches"})
    assert len(list(visit_renderers)) > 0
    # TODO look for callback

    _save_and_check_viewable_html(viewable)


def test_add_hovertext():
    """Test that add_hovertext attaches a HoverTool to visit patches."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_hovertext()
    viewable = builder.build()

    hover_tools = list(viewable.select({"type": bokeh.models.HoverTool}))
    assert len(hover_tools) > 0

    _save_and_check_viewable_html(viewable)


def test_add_footprint():
    footprint_depth_by_band = get_current_footprint(FOOTPRINT_NSIDE)[0]
    bands_in_footprint = tuple(footprint_depth_by_band.dtype.fields.keys())
    footprint_depth = footprint_depth_by_band[bands_in_footprint[0]]
    for band in bands_in_footprint[1:]:
        footprint_depth = footprint_depth + footprint_depth_by_band[band]

    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_footprint(footprint_depth)
    viewable = builder.build()

    for rend_name in ("footprint_high", "footprint_low"):
        footprint_renderers = list(viewable.select({"name": rend_name}))
        assert len(footprint_renderers) > 0

    _save_and_check_viewable_html(viewable)


def test_add_footprint_outlines():
    footprint_regions = get_current_footprint(FOOTPRINT_NSIDE)[1]

    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_footprint_outlines(footprint_regions)
    viewable = builder.build()

    assert len(_select_footprint_outline_renderers(viewable)) > 0

    _save_and_check_viewable_html(viewable)


def test_compute_footprint_outlines():
    """Test that region names are grouped and tiny loops discarded."""
    footprint = _make_outline_test_footprint()
    outlines = VisitMapBuilder._compute_footprint_outlines(footprint)

    assert isinstance(outlines, pd.DataFrame)
    assert list(outlines.index.names) == ["region", "loop"]
    assert {"RA", "decl"}.issubset(outlines.columns)

    # "lowdust" is grouped into "WFD", and "nes" and "virgo" into "other".
    assert set(outlines.index.get_level_values("region")) == {"WFD", "other"}

    # The isolated "virgo" pixel traces a loop of only a handful of
    # vertices, which should have been dropped.
    assert outlines.groupby(["region", "loop"]).size().min() >= 10


def test_compute_footprint_outlines_does_not_modify_footprint():
    """Test that computing outlines leaves the footprint passed in alone."""
    footprint = _make_outline_test_footprint()
    original_footprint = footprint.copy()

    VisitMapBuilder._compute_footprint_outlines(footprint)

    assert np.array_equal(footprint, original_footprint)


def test_compute_footprint_outlines_caches_tracing():
    """Test that footprints with equal contents share a cached tracing."""
    VisitMapBuilder._trace_footprint_outlines.cache_clear()
    footprint = _make_outline_test_footprint()

    outlines = VisitMapBuilder._compute_footprint_outlines(footprint)
    assert VisitMapBuilder._trace_footprint_outlines.cache_info().misses == 1

    # An equal footprint in a different array still hits the cache.
    equal_outlines = VisitMapBuilder._compute_footprint_outlines(footprint.copy())
    cache_info = VisitMapBuilder._trace_footprint_outlines.cache_info()
    assert cache_info.misses == 1
    assert cache_info.hits == 1
    pd.testing.assert_frame_equal(outlines, equal_outlines)

    # A footprint with different contents must be traced afresh.
    different_footprint = footprint.copy()
    different_footprint[1] = "lowdust"
    VisitMapBuilder._compute_footprint_outlines(different_footprint)
    assert VisitMapBuilder._trace_footprint_outlines.cache_info().misses == 2


def test_compute_footprint_outlines_returns_independent_outlines():
    """Test that modifying returned outlines does not corrupt the cache."""
    footprint = _make_outline_test_footprint()

    outlines = VisitMapBuilder._compute_footprint_outlines(footprint)
    original_ra = outlines["RA"].copy()
    outlines["RA"] = np.nan

    fresh_outlines = VisitMapBuilder._compute_footprint_outlines(footprint)

    assert fresh_outlines is not outlines
    pd.testing.assert_series_equal(fresh_outlines["RA"], original_ra)


def test_add_footprint_outlines_reuses_cached_tracing():
    """Test that maps built from one footprint only trace it once."""
    VisitMapBuilder._trace_footprint_outlines.cache_clear()
    footprint = _make_outline_test_footprint()

    first_builder = VisitMapBuilder(TEST_VISITS)
    first_builder.add_footprint_outlines(footprint)
    assert VisitMapBuilder._trace_footprint_outlines.cache_info().misses == 1

    second_builder = VisitMapBuilder(TEST_VISITS)
    second_builder.add_footprint_outlines(footprint)
    cache_info = VisitMapBuilder._trace_footprint_outlines.cache_info()
    assert cache_info.misses == 1
    assert cache_info.hits == 1

    # Reusing the tracing must still draw the outlines on each map.
    first_renderers = _select_footprint_outline_renderers(first_builder.build())
    second_viewable = second_builder.build()
    second_renderers = _select_footprint_outline_renderers(second_viewable)
    assert len(first_renderers) > 0
    assert len(second_renderers) == len(first_renderers)

    _save_and_check_viewable_html(second_viewable)


def test_add_alt_visit_patches():
    """Test that add_alt_visit_patches adds alternate visit patches."""

    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_alt_visit_patches(TEST_ALT_VISITS)
    viewable = builder.build()

    # Check that alt_visit_patches were added
    alt_visit_patches = list(viewable.select({"name": "alt_visit_patches"}))
    assert len(alt_visit_patches) > 0

    # Verify that the patches have the correct class and styling
    for renderer in alt_visit_patches:
        assert isinstance(renderer, bokeh.models.renderers.glyph_renderer.GlyphRenderer)
        assert renderer.glyph.fill_alpha == 0.0
        assert renderer.glyph.line_alpha == 1.0
        assert renderer.glyph.line_color is not None

    _save_and_check_viewable_html(viewable)


def test_add_alt_visits_selector():
    """Test that add_alt_visits_selector adds a Bokeh Select widget
    with correct options."""

    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_alt_visit_patches(TEST_ALT_VISITS)
    builder.add_alt_visits_selector()
    viewable = builder.build()

    # Check that the selector was added
    selector_renderers = list(viewable.select({"name": "alt_visits_selector"}))
    assert len(selector_renderers) > 0

    # Verify it's a bokeh Select widget
    selector = selector_renderers[0]
    assert isinstance(selector, bokeh.models.Select)

    # Verify the options are correctly set
    # The selector should have options based on sim_index values in the data
    expected_options = [("1", "Sim 1 Label")]  # Based on the sim_index=1 and label provided
    assert selector.options == expected_options

    _save_and_check_viewable_html(viewable)


def test_add_play_controls():
    """Test that add_play_controls adds a play/pause toggle button."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    builder.add_play_controls(name="playbutton")
    viewable = builder.build()

    # Check that the play control was added to the reference map controls
    assert "play" in builder.ref_map.controls
    play_control = builder.ref_map.controls["play"]
    assert isinstance(play_control, bokeh.models.Toggle)

    # Check that it appears in the viewable
    playbuttons = list(viewable.select({"name": "playbutton"}))
    assert len(playbuttons) > 0

    # Check that the label contains the play symbol
    assert "\u23f5 Play" in play_control.label

    # Verify the viewable can be saved to HTML
    _save_and_check_viewable_html(viewable)


def test_add_zenith_button():
    """Test that add_zenith_button adds the center zenith button."""
    builder = VisitMapBuilder(TEST_VISITS)
    builder.add_visit_patches()
    builder.add_zenith_button(name="zenithbutton")
    viewable = builder.build()

    # Check that the play control was added to the reference map controls
    assert "zenith" in builder.ref_map.controls
    play_control = builder.ref_map.controls["zenith"]
    assert isinstance(play_control, bokeh.models.Button)

    # Check that it appears in the viewable
    zenith_buttons = list(viewable.select({"name": "zenithbutton"}))
    assert len(zenith_buttons) > 0

    # Verify the viewable can be saved to HTML
    _save_and_check_viewable_html(viewable)


def test_add_coord_sys_selector():
    """Test that add_coord_sys_selector adds a coordinate system selector."""
    # Prepare a builder with the controls that add_coord_sys_selector expects
    builder = VisitMapBuilder(TEST_VISITS).add_visit_patches().add_eq_sliders()

    # Add the coordinate system selector
    builder.add_coord_sys_selector()
    viewable = builder.build()

    # Check that the selector was added to the reference map controls
    assert "coordsys" in builder.ref_map.controls
    coordsys_selector = builder.ref_map.controls["coordsys"]
    assert isinstance(coordsys_selector, bokeh.models.RadioButtonGroup)
    assert coordsys_selector.name == "Coordinate system"

    # Check that the selector appears in the viewable
    coordsys_selectors = list(viewable.select({"name": "Coordinate system"}))
    assert len(coordsys_selectors) > 0

    # Verify the viewable can be saved to HTML
    _save_and_check_viewable_html(viewable)


def test_build_with_nightsum_layout():
    """Test a build with layout='nightsum'."""

    builder = (
        VisitMapBuilder(TEST_VISITS)
        .add_visit_patches()
        .add_datetime_slider(name="datetime")
        .add_eq_sliders()
        .add_play_controls(name="play")
        .add_zenith_button(name="zenith")
        .add_coord_sys_selector()
    )
    viewable = builder.build(layout="nightsum")

    play_controls = list(viewable.select({"name": "play"}))
    assert len(play_controls) > 0

    datetime_sliders = list(viewable.select({"name": "datetime"}))
    assert len(datetime_sliders) > 0

    zenith_button = list(viewable.select({"name": "zenith"}))
    assert len(zenith_button) > 0

    coordsys_selectors = list(viewable.select({"name": "Coordinate system"}))
    assert len(coordsys_selectors) > 0

    _save_and_check_viewable_html(viewable)
