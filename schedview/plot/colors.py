import bokeh.core.property
import bokeh.transform

# Follow RTN-045 for mapping filters to plot colors

PLOT_BAND_COLORS = {
    "u": "#0c71ff",
    "g": "#49be61",
    "r": "#c61c00",
    "i": "#ffc200",
    "z": "#f341a2",
    "y": "#5d0000",
}

# Use
# glasbey.extend_palette(
#    PLOT_BAND_COLORS.values(),
#    palette_size=48,
#    colorblind_safe=True,
#    grid_size=256
# )
# to generate extra colors, attempting to get distinguishable ones, even
# for the color blind.
EXTRA_COLORS = [
    "#0000b6",
    "#04e9ff",
    "#006200",
    "#750065",
    "#ff3ce6",
    "#d75d47",
    "#bc3c7f",
    "#04f0bd",
    "#6302ac",
    "#b408b9",
    "#81b000",
    "#ff79b9",
    "#640500",
    "#65a9ff",
    "#b20000",
    "#00f468",
    "#009236",
    "#0135ff",
    "#2ac879",
    "#d43cff",
    "#ff864e",
    "#95085e",
    "#ff95ff",
    "#f721b0",
    "#9401d0",
    "#ad0e8a",
    "#370091",
    "#7c04ff",
    "#7a0890",
    "#bf54b1",
    "#f94f00",
    "#b45900",
    "#d783ff",
    "#0893d7",
    "#b4c900",
    "#862113",
    "#8f5bd0",
    "#fe75d6",
    "#1aaf49",
    "#006bbb",
    "#0c03fb",
    "#7b9000",
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
