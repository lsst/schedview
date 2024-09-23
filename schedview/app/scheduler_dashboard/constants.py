import importlib.resources

import bokeh

# Change styles using CSS variables.
h1_stylesheet = """
:host {
  --mono-font: Helvetica;
  color: white;
  font-size: 16pt;
  font-weight: 500;
}
"""
h2_stylesheet = """
:host {
  --mono-font: Helvetica;
  color: white;
  font-size: 14pt;
  font-weight: 300;
}
"""
h3_stylesheet = """
:host {
  --mono-font: Helvetica;
  color: white;
  font-size: 13pt;
  font-weight: 300;
}
"""

DEFAULT_TIMEZONE = "UTC"  # "America/Santiago"
LOGO = "/schedview-snapshot/assets/lsst_white_logo.png"
COLOR_PALETTES = [color for color in bokeh.palettes.__palettes__ if "256" in color]
DEFAULT_COLOR_PALETTE = "Viridis256"
DEFAULT_NSIDE = 16
PACKAGE_DATA_DIR = importlib.resources.files("schedview.data").as_posix()
LFA_DATA_DIR = "s3://rubin:"
