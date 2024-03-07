import astropy
import astropy.units as u
import cartopy
import cartopy.crs as ccrs
import colorcet
import healpy as hp
import matplotlib as mpl
import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord

DEFAULT_MERIDIANS = np.arange(-180, 210, 30.0)
DEFAULT_PARALLELS = np.arange(-60, 90.0, 30.0)
EARTH_DIAMETER = 2 * astropy.constants.R_earth.to(u.m).value
PC = ccrs.PlateCarree()
LAEA_SOUTH = ccrs.LambertAzimuthalEqualArea(central_longitude=0, central_latitude=-89.99)


def compute_circle_points(
    center_ra,
    center_decl,
    radius=90.0,
    start_bear=0,
    end_bear=360,
    step=1,
):
    """Create points along a circle or arc on a sphere

    Parameters
    ----------
    center_ra : `float`
        R.A. of the center of the circle (deg.).
    center_decl : `float`
        Decl. of the center of the circle (deg.).
    radius : float, optional
        Radius of the circle (deg.), by default 90.0
    start_bear : int, optional
        Bearing (E. of N.) of the start of the circle (deg.), by default 0
    end_bear : int, optional
        Bearing (E. of N.) of the end of the circle (deg.), by default 360
    step : int, optional
        Spacing of the points along the circle (deg.), by default 1

    Returns
    -------
    circle : `pandas.DataFrame`
        DataFrame with points in the circle.
    """
    ras = []
    decls = []

    bearing_angles = np.arange(start_bear, end_bear + step, step) * u.deg
    center_coords = SkyCoord(center_ra * u.deg, center_decl * u.deg)
    circle_coords = center_coords.directional_offset_by(bearing_angles, radius * u.deg)
    bearings = bearing_angles.value.tolist()
    ras = circle_coords.ra.deg.tolist()
    decls = circle_coords.dec.deg.tolist()

    # de-normalize RA so there are no large jumps, which can
    # confuse cartopy + matplotlib

    previous_ra = ras[0]
    for ra_index in range(1, len(ras)):
        if ras[ra_index] - previous_ra > 180:
            ras[ra_index] -= 360
        if ras[ra_index] - previous_ra < -180:
            ras[ra_index] += 360
        previous_ra = ras[ra_index]

    circle = pd.DataFrame(
        {
            "bearing": bearings,
            "ra": ras,
            "decl": decls,
        }
    ).set_index("bearing")

    return circle


def sky_map(
    axes,
    parallels=DEFAULT_PARALLELS,
    meridians=DEFAULT_MERIDIANS,
    full_sky=True,
    west_right=True,
    label_parallels=True,
    label_meridians=True,
    south=True,
    grid_color="gray",
):
    """Turn a set of matplotlib axes into a sky map.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    parallels : `numpy.ndarray`
        An array specifying the locations of graticule parallels, in
        degrees. Defaults to every 30 degrees.
    meridians : `numpy.ndarray`
        An array specifying the locations of graticule meridians, in
        degrees. Defaults to every 30 degrees.
    full_sky : `bool`
        Show the full sky, not just where there is data. Defaults to True.
    west_right : `bool`
        Show west to the right (the surface of a sphere as seen from the
        inside, as in standing on the earth looking at the sky) rather than
        to the left (the surface of a sphere as seen from the outside, as
        in looking down on a the Earth). Defaults to True.
    label_parallels : `bool`
        Show labels on the parallel graticules. Defaults to True.
    label_meridians : `bool`
        Show labels on the meridian graticules. Defaults to True.
    south : `bool`
        If True, place the south equatorial pole at the center (if True).
        If False place the north equatorial pole at the center.
        Defaults to True.
    grid_color : `str`
        The color for the graticules. Defaults to `gray`.
    """
    if full_sky:
        # Cartopy was designed for geography, so it scales to units of
        # meters on the Earth.
        axes.set_xlim(-1 * EARTH_DIAMETER, EARTH_DIAMETER)
        axes.set_ylim(-1 * EARTH_DIAMETER, EARTH_DIAMETER)

    if west_right:
        axes.set_xlim(reversed(axes.get_xlim()))

    gl = axes.gridlines(crs=PC, draw_labels=False, color=grid_color)
    gl.xlocator = mpl.ticker.FixedLocator(meridians)
    gl.ylocator = mpl.ticker.FixedLocator(parallels)
    gl.xformatter = cartopy.mpl.gridliner.LONGITUDE_FORMATTER
    gl.yformatter = cartopy.mpl.gridliner.LATITUDE_FORMATTER

    meridian_label = np.array([0, 90, 180, 270])
    if label_meridians:
        if south:
            meridian_label_dec = 89
            m = meridian_label[0]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="center",
                verticalalignment="bottom",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[1]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="right",
                verticalalignment="center",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[2]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="center",
                verticalalignment="top",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[3]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="left",
                verticalalignment="center",
                color=grid_color,
                transform=PC,
            )
        else:
            meridian_label_dec = -89
            m = meridian_label[0]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="center",
                verticalalignment="top",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[1]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="right",
                verticalalignment="center",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[2]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="center",
                verticalalignment="bottom",
                color=grid_color,
                transform=PC,
            )
            m = meridian_label[3]
            axes.text(
                m,
                meridian_label_dec,
                r"$%d^\circ$" % m,
                horizontalalignment="left",
                verticalalignment="center",
                color=grid_color,
                transform=PC,
            )

    if label_parallels:
        for p in parallels:
            if p < 60:
                axes.text(
                    270 - 90,
                    p,
                    r"$%d^\circ$" % p,
                    horizontalalignment="left",
                    verticalalignment="top",
                    color=grid_color,
                    weight="bold",
                    transform=PC,
                )


def map_healpix(axes, hp_map, resolution=None, scale_limits=None, **in_kwargs):
    """Show healpixels on a set of GeoAxes.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    hp_map : `numpy.ndarray` or `numpy.ma.MaskedArray`
        An array of healpixes values.
    resolution : `float` or `None`
        The resolution onto which to sample healpixel points (deg/pixel).
        None sets it according to the nside of the healpix map.
        Defaults to None.
    scale_limits : `list` [`float`] or `None`
        The minimum and maximum values to map to color values.
        None sets it dynamically using `astropy.visualization.ZScaleInterval`
        Defaults to None.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.imshow`.
    """
    kwargs = {"cmap": colorcet.cm.blues}
    kwargs.update(in_kwargs)

    nside = hp.npix2nside(hp_map.size)
    if resolution is None:
        resolution = hp.max_pixrad(nside, degrees=True) / 4

    ra, decl = np.meshgrid(np.arange(-180, 180, resolution), np.arange(-90, 90, resolution))

    if scale_limits is None:
        try:
            unmasked_hpix = hp_map[~hp_map.mask]
        except AttributeError:
            # this array doesn't have a mask
            unmasked_hpix = hp_map

        scale_limits = astropy.visualization.ZScaleInterval().get_limits(unmasked_hpix)

    im = hp_map[hp.ang2pix(nside, ra, decl, lonlat=True)]

    axes.imshow(
        im, extent=(-180, 180, 90, -90), transform=PC, vmin=scale_limits[0], vmax=scale_limits[1], **kwargs
    )


def plot_ecliptic(axes, **kwargs):
    """Plot the ecliptic plane on a set of GeoAxes.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.plot`.
    """
    ecliptic_pole = SkyCoord(lon=0 * u.degree, lat=90 * u.degree, frame="geocentricmeanecliptic").icrs
    points_on_ecliptic = compute_circle_points(ecliptic_pole.ra.deg, ecliptic_pole.dec.deg)
    axes.plot(points_on_ecliptic.ra, points_on_ecliptic.decl, **kwargs)


def plot_galactic_plane(axes, **kwargs):
    """Plot the galactic plane on a set of GeoAxes.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.plot`.
    """
    galactic_pole = SkyCoord(l=0 * u.degree, b=90 * u.degree, frame="galactic").icrs
    points_on_galactic_plane = compute_circle_points(galactic_pole.ra.deg, galactic_pole.dec.deg)
    axes.plot(points_on_galactic_plane.ra, points_on_galactic_plane.decl, **kwargs)


def plot_sun(axes, model_observatory, night_events, **kwargs):
    """Plot the sun on a set of GeoAxes.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    model_observatory : `ModelObservatory`
        The model observatory (which supplies the location and sun position).
    night_events : `pd.DataFrame`
        A table of almanac events for the night, as generated by
        `schedview.compute.astro.night_events`.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.scatter`.
    """
    mjd = night_events.loc["night_middle", "MJD"]
    sun_moon_positions = model_observatory.almanac.get_sun_moon_positions(mjd)
    sun_ra = np.degrees(sun_moon_positions["sun_RA"].item())
    sun_decl = np.degrees(sun_moon_positions["sun_dec"].item())
    axes.scatter(sun_ra, sun_decl, **kwargs)


def plot_moon(axes, model_observatory, night_events, **kwargs):
    """Plot the moon at the start, middle, and end of night
    on a set of GeoAxes.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    model_observatory : `ModelObservatory`
        The model observatory (which supplies the location and sun position).
    night_events : `pd.DataFrame`
        A table of almanac events for the night, as generated by
        `schedview.compute.astro.night_events`.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.scatter`.
    """
    mjd = night_events.loc[["sunset", "night_middle", "sunrise"], "MJD"]
    sun_moon_positions = model_observatory.almanac.get_sun_moon_positions(mjd)
    sun_ra = np.degrees(sun_moon_positions["moon_RA"])
    sun_decl = np.degrees(sun_moon_positions["moon_dec"])
    axes.scatter(sun_ra, sun_decl, **kwargs)


def plot_horizons(axes, night_events, latitude, zd=90, **kwargs):
    """Plot the limits of what can be observed at a given zenith distance
    on a night.

    Parameters
    ----------
    axes : `cartopy.mpl.geoaxes.GeoAxes`
        A matplotlib set of axes with a cartopy transform specifying the
        projection.
    night_events : `pd.DataFrame`
        A table of almanac events for the night, as generated by
        `schedview.compute.astro.night_events`.
    latitute : `float`
        The latitude of the observatory, in degrees.
    zd : `float`
        The highest observable zenith distance, in degrees.
        Defaults to 90.
    **kwargs
        Additional keyword arguments are passed to
        `cartopy.mpl.geoaxes.GeoAxes.scatter`.
    """
    evening = compute_circle_points(night_events.loc["sun_n12_setting", "LST"], latitude, zd, 180, 380)
    axes.plot(evening.ra, evening.decl, **kwargs)

    morning = compute_circle_points(night_events.loc["sun_n12_rising", "LST"], latitude, zd, 0, 180)
    axes.plot(morning.ra, morning.decl, **kwargs)
