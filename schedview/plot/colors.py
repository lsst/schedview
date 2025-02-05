import bokeh.core.property
import bokeh.transform

# Follow RTN-045 for mapping filters to plot colors

PLOT_BAND_COLORS = {
    "u": "#56b4e9",
    "g": "#008060",
    "r": "#ff4000",
    "i": "#850000",
    "z": "#6600cc",
    "y": "#000000",
}


def make_band_cmap(field_name="band") -> bokeh.core.property.vectorization.Field:
    """Make a bokeh cmap transform for bands

    Parameters
    ----------
    field_name : `str`
        Name of field with the band value.

    Returns
    -------
    cmap : `bokeh.core.property.vectorization.Field`
        The bokeh color map.
    """
    cmap = bokeh.transform.factor_cmap(
        field_name, tuple(PLOT_BAND_COLORS.values()), tuple(PLOT_BAND_COLORS.keys())
    )
    return cmap
