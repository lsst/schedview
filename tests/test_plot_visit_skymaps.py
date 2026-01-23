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
        "fieldRA": [10.0, 20.0],
        "fieldDec": [-5.0, 15.0],
        "observationStartMJD": [59000.0, 59001.0],
        "band": ["g", "r"],
        "rotSkyPos": [0.0, 45.0],
        "observationId": [1, 2],
        "start_timestamp": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "observationStartLST": [150.0, 160.0],
        "paraAngle": [0.0, 0.0],
        "azimuth": [180.0, 190.0],
        "altitude": [45.0, 50.0],
        "observation_reason": ["science", "science"],
        "science_program": ["prog1", "prog2"],
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
    builder.hide_future_visits()
    viewable = builder.build()

    visit_renderers = viewable.select({"name": "visit_patches"})
    assert len(list(visit_renderers)) > 0
    # TODO look for callback

    _save_and_check_viewable_html(viewable)


def test_highlight_recent_visits():
    """Test that highlight_recent_visits applies its transform."""
    builder = VisitMapBuilder(TEST_VISITS)
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
    outline_renderers = [
        m
        for m in viewable.select({"type": bokeh.models.GlyphRenderer})
        if m.name.startswith("footprint_outline")
    ]
    assert len(outline_renderers) > 0

    _save_and_check_viewable_html(viewable)
