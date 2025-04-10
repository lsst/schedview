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

# Extra colors from the same Glasbey palette from which the RTN-045
# colors were drawn:
#  glasbey.create_palette(
#     palette_size=12,
#     colorblind_safe=True,
#     cvd_severity=100
#  )
# So, these should be distinct, even for color blind users,
# to the extent glasbey can do it.
EXTRA_COLORS = ["#3d7555", "#20ebff", "#0400fb", "#102da2", "#4171ff", "#791059", "#f335e7"]


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
