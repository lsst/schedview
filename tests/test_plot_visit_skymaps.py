"""Unit tests for schedview.plot.visit_skymaps module."""

import pathlib
import tempfile

import bokeh.io
import bokeh.models
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

    # Bokeh does not support pattern matching in selection by name,
    # so iterate over all renderers and check their names explicitly.
    outline_renderers = []
    for renderer in viewable.select({"type": bokeh.models.GlyphRenderer}):
        assert isinstance(renderer.name, str)
        if renderer.name.startswith("footprint_outline"):
            outline_renderers.append(renderer)

    assert len(outline_renderers) > 0

    _save_and_check_viewable_html(viewable)


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
