import base64
from io import BytesIO

import matplotlib as mpl

__all__ = ["mpl_fig_to_html"]


def mpl_fig_to_html(
    fig: mpl.figure.Figure, template: str = '<img src="data:image/png;base64,{png_base64}" />'
) -> str:
    """Convert a Matplotlib figure to an HTML ``<img>`` tag.

    Parameters
    ----------
    fig: `matplotlib.figure.Figure`
        The figure instance to be rendered.
    template: `str`, optional
        A format string that will receive the base64‑encoded PNG data.
        The default template embeds the image in a data URI inside an ``<img>``
        element.

    Returns
    -------
    fig_html: `str`
        An HTML snippet containing the figure encoded as a base64 PNG.
    """
    byte_buffer = BytesIO()
    fig.savefig(byte_buffer, format="png")
    byte_buffer.seek(0)
    png_base64 = base64.b64encode(byte_buffer.read()).decode("utf-8")
    fig_html = template.format(png_base64=png_base64)
    return fig_html
