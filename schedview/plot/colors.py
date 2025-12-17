import bokeh.core.property
import bokeh.transform

# Follow RTN-045 for mapping filters to plot colors

PLOT_BAND_COLORS = {
    "u": "#1600ea",
    "g": "#31de1f",
    "r": "#b52626",
    "i": "#370201",
    "z": "#ba52ff",
    "y": "#61a2b3",
}

# Use
# glasbey.extend_palette(
#    PLOT_BAND_COLORS.values(),
#    palette_size=48,
#    colorblind_safe=True,
#    grid_size=256
# )
# to generate extra colors, attempting to get distinguishable ones.
EXTRA_COLORS = [
    "#007000",
    "#ff8c72",
    "#006169",
    "#000073",
    "#9461ff",
    "#002e00",
    "#d8a2ff",
    "#26af00",
    "#dc1a25",
    "#36164c",
    "#10d9aa",
    "#48936f",
    "#0113ff",
    "#84010e",
    "#9d7cb5",
    "#01593c",
    "#7c3ca8",
    "#e2b200",
    "#015cff",
    "#924e47",
    "#00b2fd",
    "#81c9d3",
    "#ff5701",
    "#2b8683",
    "#00457c",
    "#c87168",
    "#0ed767",
    "#0080aa",
    "#7c7f31",
    "#3702a6",
    "#364801",
    "#983e00",
    "#5dae9d",
    "#540005",
    "#79a762",
    "#c073f8",
    "#0d7849",
    "#280162",
    "#73a9c9",
    "#013ed6",
    "#5a3c71",
    "#9804f1",
]


def make_band_cmap(
    field_name="band", bands=("u", "g", "r", "i", "z", "y")
) -> bokeh.core.property.vectorization.Field:
    """Make a bokeh cmap transform for bands

    Parameters
    ----------
    field_name : `str`
        Name of field with the band value.
    bands : `list`
        A full list of bands that need colors.

    Returns
    -------
    cmap : `bokeh.core.property.vectorization.Field`
        The bokeh color map.
    """
    # Always assign standard colors to standard bands
    assigned_colors, assigned_bands = list(PLOT_BAND_COLORS.values()), list(PLOT_BAND_COLORS.keys())

    # Go through any we miss and assign extra colors to extra bands.
    for extra_index, band in enumerate(set(bands)):
        if band not in assigned_bands:
            assigned_bands.append(band)
            assigned_colors.append(EXTRA_COLORS[extra_index % len(EXTRA_COLORS)])

    cmap = bokeh.transform.factor_cmap(field_name, tuple(assigned_colors), tuple(assigned_bands))
    return cmap
