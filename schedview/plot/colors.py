import bokeh.transform

# Follow RTN-045 for mapping filters to plot colors

PLOT_FILTER_COLORS = {
    "u": "#56b4e9",
    "g": "#008060",
    "r": "#ff4000",
    "i": "#850000",
    "z": "#6600cc",
    "y": "#000000",
}

PLOT_FILTER_CMAP = bokeh.transform.factor_cmap(
    "filter", tuple(PLOT_FILTER_COLORS.values()), tuple(PLOT_FILTER_COLORS.keys())
)
