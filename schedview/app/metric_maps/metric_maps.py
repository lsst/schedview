import bokeh.plotting

from rubin_sim import maf

from spheremap import ArmillarySphere, Planisphere, MollweideMap
from schedview.collect.stars import load_bright_stars
from schedview.collect import get_metric_path


def make_metric_figure(metric_values_fname=None, nside=32, mag_limit_slider=True):
    """Create a figure showing multiple projections of a set of a MAF metric.

    Parameters
    ----------
    metric_values_fname : `str`, optional
        Name of file from which to load metric values, as saved by MAF
        in a saved metric bundle. If it is None, the look for the
        file name in the ``METRIC_FNAME`` environment varable. By default None
    nside : `int`, optional
        Healpix nside to use for display, by default 8
    mag_limit_slider : `bool`, optional
        Show the mag limit slider for stars?, by default True

    Returns
    -------
    fig : `bokeh.models.layouts.LayoutDOM`
        A bokeh figure that can be displayed in a notebook (e.g. with
        ``bokeh.io.show``) or used to create a bokeh app.

    Notes
    -----
    If ``mag_limit_slider`` is ``True``, it creates a magnitude limit
    slider for the stars. This is implemented as a python callback, and
    so is only operational in full bokeh app, not standalone output.
    """

    if metric_values_fname is None:
        metric_values_fname = get_metric_path()

    healpy_values = maf.MetricBundle.load(metric_values_fname).metric_values

    star_data = load_bright_stars().loc[:, ["name", "ra", "decl", "Vmag"]]
    star_data["glyph_size"] = 15 - (15.0 / 3.5) * star_data["Vmag"]
    star_data.query("glyph_size>0", inplace=True)

    arm = ArmillarySphere()
    hp_ds, cmap, _ = arm.add_healpix(healpy_values, nside=nside)
    hz = arm.add_horizon()
    zd70 = arm.add_horizon(zd=70, line_kwargs={"color": "red", "line_width": 2})
    star_ds = arm.add_stars(
        star_data, mag_limit_slider=mag_limit_slider, star_kwargs={"color": "black"}
    )
    arm.decorate()

    pla = Planisphere()
    pla.sliders["mjd"] = arm.sliders["mjd"]
    pla.add_healpix(hp_ds, cmap=cmap, nside=nside)
    pla.add_horizon(data_source=hz)
    pla.add_horizon(
        zd=60, data_source=zd70, line_kwargs={"color": "red", "line_width": 2}
    )
    pla.add_stars(
        star_data,
        data_source=star_ds,
        mag_limit_slider=False,
        star_kwargs={"color": "black"},
    )
    pla.decorate()

    mol_plot = bokeh.plotting.figure(
        frame_width=512, frame_height=256, match_aspect=True
    )
    mol = MollweideMap(plot=mol_plot)
    mol.sliders["mjd"] = arm.sliders["mjd"]
    mol.add_healpix(hp_ds, cmap=cmap, nside=nside)
    mol.add_horizon(data_source=hz)
    mol.add_horizon(
        zd=70, data_source=zd70, line_kwargs={"color": "red", "line_width": 2}
    )
    mol.add_stars(
        star_data,
        data_source=star_ds,
        mag_limit_slider=False,
        star_kwargs={"color": "black"},
    )
    mol.decorate()

    figure = bokeh.layouts.row(
        bokeh.layouts.column(mol.plot, *arm.sliders.values()), arm.plot, pla.plot
    )

    return figure


def add_metric_app(doc):
    """Add a metric figure to a bokeh document

    Parameters
    ----------
    doc : `bokeh.document.document.Document`
        The bokeh document to which to add the figure.
    """
    figure = make_metric_figure()
    doc.add_root(figure)


if __name__.startswith("bokeh_app_"):
    doc = bokeh.plotting.curdoc()
    add_metric_app(doc)
