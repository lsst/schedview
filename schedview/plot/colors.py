import bokeh.core.property
import bokeh.transform
from lsst.utils.plotting import get_multiband_plot_colors

# Follow RTN-045 for mapping filters to plot colors

PLOT_BAND_COLORS = get_multiband_plot_colors()
LIGHT_PLOT_BAND_COLORS = get_multiband_plot_colors(dark_background=True)

# to generate extra colors for no filter, pinhole, etc.,
# attempting to get distinguishable ones.

# Extended palettes as they were on 2026-02-17
EXTRA_COLORS = [
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
LIGHT_EXTRA_COLORS = [
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

need_new_standard_colors = EXTRA_COLORS[: len(PLOT_BAND_COLORS)] != list(PLOT_BAND_COLORS.values())
need_new_light_colors = LIGHT_EXTRA_COLORS[: len(LIGHT_PLOT_BAND_COLORS)] != list(
    LIGHT_PLOT_BAND_COLORS.values()
)

if need_new_standard_colors or need_new_light_colors:
    try:
        # Start by trying to use glasbey to get colors distinguishable from
        # the latest standards from lsst.utils.plotting

        import glasbey

        if need_new_standard_colors:
            EXTRA_COLORS = glasbey.extend_palette(
                PLOT_BAND_COLORS.values(), palette_size=48, colorblind_safe=True, grid_size=256
            )

        if need_new_light_colors:
            LIGHT_EXTRA_COLORS = glasbey.extend_palette(
                LIGHT_PLOT_BAND_COLORS.values(), palette_size=48, colorblind_safe=True, grid_size=256
            )

    except ModuleNotFoundError:
        # If glasbey is not available, use lists of extra colors based on the
        # standadards as they were on 2026-02-17
        EXTRA_COLORS[: len(PLOT_BAND_COLORS)] = PLOT_BAND_COLORS.values()
        LIGHT_EXTRA_COLORS[: len(LIGHT_PLOT_BAND_COLORS)] = LIGHT_PLOT_BAND_COLORS.values()


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
