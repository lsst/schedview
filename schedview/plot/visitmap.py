import numpy as np
import healpy as hp
import bokeh
from astropy.time import Time

import schedview.collect.scheduler_pickle
from schedview.plot.SphereMap import Planisphere, ArmillarySphere
from rubin_sim.scheduler.model_observatory.model_observatory import ModelObservatory
import schedview.compute.astro
from schedview.collect.stars import load_bright_stars

BAND_COLORS = dict(
    u="#56b4e9", g="#008060", r="#ff4000", i="#850000", z="#6600cc", y="#000000"
)

def plot_visit_skymaps(visits, footprint, conditions):
    """Plot visits on a map of the sky.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        One row per visit, with at least the following columns:
        
        ``"fieldRA"``
            The visit R.A. in degrees (`float`).
        ``"fieldDec"``
            The visit declination in degrees (`float`).
        ``"observationStartMJD"``
            The visit start MJD (`float`).
        ``"filter"``
            The visit filter (`str`)
         
    footprint : `numpy.array`
        A healpix map of the footprint.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`
        The conditions for the night, which determines the start and end
        times covered by the map.

    Returns
    -------
    _type_
        _description_
    """    

    band_sizes = {"u": 15, "g": 13, "r": 11, "i": 9, "z": 7, "y": 5}

    psphere = Planisphere(mjd=conditions.mjd)

    asphere = ArmillarySphere(mjd=conditions.mjd)

    cmap = bokeh.transform.linear_cmap(
        "value", "Greys256", int(np.ceil(np.nanmax(footprint) * 2)), 0
    )
    nside = hp.npix2nside(footprint.shape[0])
    healpix_ds, cmap, glyph = asphere.add_healpix(footprint, nside=nside, cmap=cmap)
    psphere.add_healpix(healpix_ds, nside=nside, cmap=cmap)
    for band in "ugrizy":
        band_visits = visits.query(f"filter == '{band}'")
        visit_ds = asphere.add_marker(
            ra=band_visits.fieldRA,
            decl=band_visits.fieldDec,
            glyph_size=band_sizes[band],
            name=band_visits.index.values,
            min_mjd=band_visits.observationStartMJD.values,
            circle_kwargs={
                "fill_alpha": "in_mjd_window",
                "fill_color": BAND_COLORS[band],
                "line_alpha": 0,
            },
        )
        psphere.add_marker(
            data_source=visit_ds,
            glyph_size=band_sizes[band],
            name=band_visits.index.values,
            min_mjd=band_visits.observationStartMJD.values,
            circle_kwargs={
                "fill_alpha": "in_mjd_window",
                "fill_color": BAND_COLORS[band],
                "line_alpha": 0,
            },
        )
    asphere.decorate()
    psphere.decorate()
    horizon_ds = asphere.add_horizon()
    psphere.add_horizon(data_source=horizon_ds)
    horizon70_ds = asphere.add_horizon(
        zd=70, line_kwargs={"color": "red", "line_width": 2}
    )
    psphere.add_horizon(
        data_source=horizon70_ds, line_kwargs={"color": "red", "line_width": 2}
    )
    sun_ds = asphere.add_marker(
        ra=np.degrees(conditions.sunRA),
        decl=np.degrees(conditions.sunDec),
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )
    psphere.add_marker(
        data_source=sun_ds,
        name="Sun",
        glyph_size=15,
        circle_kwargs={"color": "yellow", "fill_alpha": 1},
    )

    moon_ds = asphere.add_marker(
        ra=np.degrees(conditions.moonRA),
        decl=np.degrees(conditions.moonDec),
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )
    psphere.add_marker(
        data_source=moon_ds,
        name="Moon",
        glyph_size=15,
        circle_kwargs={"color": "orange", "fill_alpha": 0.8},
    )

    star_data = load_bright_stars().loc[:, ["name", "ra", "decl", "Vmag"]]
    star_data["glyph_size"] = 15 - (15.0 / 3.5) * star_data["Vmag"]
    star_data.query("glyph_size>0", inplace=True)
    star_ds = psphere.add_stars(
        star_data, mag_limit_slider=True, star_kwargs={"color": "black"}
    )

    asphere.add_stars(
        star_data,
        data_source=star_ds,
        mag_limit_slider=False,
        star_kwargs={"color": "black"},
    )

    asphere.sliders["mjd"].start = conditions.sun_n12_setting
    asphere.sliders["mjd"].end = conditions.sun_n12_rising

    fig = bokeh.layouts.row(
        asphere.figure,
        psphere.figure,
    )
    return fig


def create_visit_skymaps(
    visits, scheduler, night_date, observatory=None, timezone="Chile/Continental"
):
    """Create a map of visits on the sky.

    Parameters
    ----------
    visits : `pandas.DataFrame` or `str`
        If a `pandas.DataFrame`, it needs at least the following columns:
        
        ``"fieldRA"``
            The visit R.A. in degrees (`float`).
        ``"fieldDec"``
            The visit declination in degrees (`float`).
        ``"observationStartMJD"``
            The visit start MJD (`float`).
        ``"filter"``
            The visit filter (`str`)
         
        If a string, the file name of the opsim database from which the
        visits should be loaded.
    scheduler : `rubin_sim.scheduler.schedulers.core_scheduler.Core_scheduler` or `str`
        The scheduler from which to extract the footprint, or the name of a file
        from which such a scheduler should be loaded.
    night_date : `astropy.time.Time`
        A time during the night to plot
    observatory : rubin_sim.scheduler.modelObservatory.model_observatory.Model_observatory`, optional
        Provides the location of the observatory, used to compute
        night start and end times.
        By default None.
    timezone : `str`, optional
        by default "Chile/Continental"

    Returns
    -------
    figure : `bokeh.models.layouts.LayoutDOM`
        The figure itself.
    data : `dict`
        The arguments used to produce the figure using
        `plot_visit_skymaps`.
    """    
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(
        night_date=night_date, site=site, timezone=timezone
    )
    start_time = Time(night_events.loc["sunset", "UTC"])
    end_time = Time(night_events.loc["sunrise", "UTC"])

    if isinstance(visits, str):
        visits = schedview.collect.opsim.read_opsim(visits)

    if start_time is not None:
        visits.query(f"observationStartMJD >= {Time(start_time).mjd}", inplace=True)

    if end_time is not None:
        visits.query(f"observationStartMJD <= {Time(end_time).mjd}", inplace=True)

    if isinstance(scheduler, str):
        scheduler, conditions = schedview.collect.scheduler_pickle.read_scheduler(
            scheduler
        )

    if observatory is None:
        observatory = ModelObservatory(nside=scheduler.nside)
    
    footprint = schedview.collect.footprint.get_greedy_footprint(scheduler)
    observatory.mjd = visits.observationStartMJD.min()
    conditions = observatory.return_conditions()
    data = {"visits": visits, "footprint": footprint, "conditions": conditions}
    vmap = schedview.plot.visitmap.plot_visit_skymaps(**data)
    return vmap, data
