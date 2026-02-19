from typing import Any, Callable, Dict

import bokeh.core.property
import bokeh.transform

try:
    from glasbey import extend_palette
except ModuleNotFoundError:

    def extend_palette(*args, **kwargs) -> Any:
        raise NotImplementedError


extend_palette: Callable[..., Any]

try:
    from lsst.utils.plotting import get_multiband_plot_colors
except ModuleNotFoundError:

    def get_multiband_plot_colors(*arg, **kwargs) -> Dict[str, str]:
        raise NotImplementedError


get_multiband_plot_colors: Callable[..., Any]

BANDS: tuple[str] = ("u", "g", "r", "i", "z", "y")

# Palettes from RTN-045 as of 2026-02-17, supplemented so we
# have extra colors for non-standard "bands" (e.g. pinhole) using
# glasbey.extend_palette with kwargs:
#   palette_size=12, colorblind_safe=True, grid_size=256
#
DEFAULT_DARK_COLORS: list[str] = [
    "#0c71ff",
    "#49be61",
    "#c61c00",
    "#ffc200",
    "#f341a2",
    "#5d0000",
    "#0000b6",
    "#04e9ff",
    "#006200",
    "#750065",
    "#e74eff",
    "#ff5f00",
]
DEFAULT_BAND_COLORS: Dict[str, str] = {b: DEFAULT_DARK_COLORS[i] for i, b in enumerate(BANDS)}

DEFAULT_LIGHT_COLORS: list[str] = [
    "#3eb7ff",
    "#30c39f",
    "#ff7e00",
    "#2af5ff",
    "#a7f9c1",
    "#fdc900",
    "#85b972",
    "#12c5c8",
    "#f2e585",
    "#fba96c",
    "#23ffdf",
    "#7ccb2b",
]
DEFAULT_LIGHT_BAND_COLORS: Dict[str, str] = {b: DEFAULT_LIGHT_COLORS[i] for i, b in enumerate(BANDS)}

PLOT_BAND_COLORS: Dict[str, str]
try:
    PLOT_BAND_COLORS = get_multiband_plot_colors()
except NotImplementedError:
    PLOT_BAND_COLORS = DEFAULT_BAND_COLORS

LIGHT_PLOT_BAND_COLORS: Dict[str, str]
try:
    LIGHT_PLOT_BAND_COLORS = get_multiband_plot_colors(dark_background=True)
except NotImplementedError:
    LIGHT_PLOT_BAND_COLORS = DEFAULT_LIGHT_BAND_COLORS

EXTRA_COLORS: list[str]
if DEFAULT_DARK_COLORS[: len(PLOT_BAND_COLORS)] == list(PLOT_BAND_COLORS.values()):
    EXTRA_COLORS = DEFAULT_DARK_COLORS
else:
    try:
        EXTRA_COLORS = extend_palette(
            PLOT_BAND_COLORS.values(), palette_size=12, colorblind_safe=True, grid_size=256
        )
    except NotImplementedError:
        EXTRA_COLORS = list(PLOT_BAND_COLORS.values()) + DEFAULT_DARK_COLORS[len(PLOT_BAND_COLORS) :]

LIGHT_EXTRA_COLORS: list[str]
if DEFAULT_LIGHT_COLORS[: len(LIGHT_PLOT_BAND_COLORS)] == list(LIGHT_PLOT_BAND_COLORS.values()):
    LIGHT_EXTRA_COLORS = DEFAULT_LIGHT_COLORS
else:
    try:
        LIGHT_EXTRA_COLORS = extend_palette(
            LIGHT_PLOT_BAND_COLORS.values(), palette_size=12, colorblind_safe=True, grid_size=256
        )
    except NotImplementedError:
        LIGHT_EXTRA_COLORS = (
            list(LIGHT_PLOT_BAND_COLORS.values()) + DEFAULT_LIGHT_COLORS[len(LIGHT_PLOT_BAND_COLORS) :]
        )


def make_band_cmap(
    field_name="band", bands=("u", "g", "r", "i", "z", "y"), light=False
) -> bokeh.core.property.vectorization.Field:
    """Make a bokeh cmap transform for bands

    Parameters
    ----------
    field_name : `str`
        Name of field with the band value.
    bands : `list`
        A full list of bands that need colors.
    light : `bool`
        Use light palette

    Returns
    -------
    cmap : `bokeh.core.property.vectorization.Field`
        The bokeh color map.
    """
    band_colors = LIGHT_PLOT_BAND_COLORS if light else PLOT_BAND_COLORS
    extra_colors = LIGHT_EXTRA_COLORS if light else EXTRA_COLORS

    # Always assign standard colors to standard bands
    assigned_colors, assigned_bands = list(band_colors.values()), list(band_colors.keys())

    # Go through any we miss and assign extra colors to extra bands.
    for extra_index, band in enumerate(set(bands)):
        if band not in assigned_bands:
            assigned_bands.append(band)
            assigned_colors.append(extra_colors[extra_index % len(extra_colors)])

    cmap = bokeh.transform.factor_cmap(field_name, tuple(assigned_colors), tuple(assigned_bands))
    return cmap
