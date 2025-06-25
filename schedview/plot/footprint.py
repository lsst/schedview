import warnings

import bokeh
import healpy as hp
import numpy as np
from uranography.api import split_healpix_by_resolution

NSIDE_LOW = 8


def add_footprint_to_skymaps(footprint, spheremaps):
    """Add the footprint to a skymap

    Parameters
    ----------
    footprint : `numpy.array`
        A healpix map of the footprint.
    spherermaps : `list` of `uranography.SphereMap`
        The map to add the footprint to
    """
    nside_low = NSIDE_LOW

    cmap = bokeh.transform.linear_cmap("value", "Greys256", int(np.ceil(np.nanmax(footprint) * 2)), 0)

    nside_high = hp.npix2nside(footprint.shape[0])
    footprint_high, footprint_low = split_healpix_by_resolution(footprint, nside_low, nside_high)

    healpix_high_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_high, nside=nside_high, cmap=cmap)
    healpix_low_ds, cmap, glyph = spheremaps[0].add_healpix(footprint_low, nside=nside_low, cmap=cmap)

    for spheremap in spheremaps[1:]:
        spheremap.add_healpix(healpix_high_ds, nside=nside_high, cmap=cmap)
        spheremap.add_healpix(healpix_low_ds, nside=nside_low, cmap=cmap)

    for spheremap in spheremaps:
        spheremap.connect_controls(healpix_high_ds)
        spheremap.connect_controls(healpix_low_ds)

    return spheremaps


def add_footprint_outlines_to_skymaps(
    footprint_polygons, spheremaps, colormap=None, filled=False, **line_kwargs
):
    """Add the footprint to a skymap

    Parameters
    ----------
    footprint_polygons : `pd.DataFrame`
        A pandas DataFrame with RA, decl columns with polygon vertices, and
        region and loop_id index levels.
    spherermaps : `list` of `uranography.SphereMap`
        The map to add the footprint to
    colormap : `dict`
        A dictionar mapping strings to colors.
    """

    if filled:
        warnings.warn(
            'The "filled" option does yet work correctly when the polygon crosses a projection discontinuity.'
        )

    if "region" not in footprint_polygons.index.names:
        footprint_polygons = footprint_polygons.assign(region="only").set_index("region", append=True).copy()

    if "loop" not in footprint_polygons.index.names:
        footprint_polygons = footprint_polygons.assign(loop=0).set_index("loop", append=True).copy()

    footprint_polygons = footprint_polygons.reorder_levels(["region", "loop"]).copy()

    outside = ""
    if colormap is None:
        regions = [r for r in footprint_polygons.index.get_level_values("region").unique() if r != outside]
        if len(regions) == 1:
            palette = ["black"]
        else:
            # Try palettes from the "colorblind" section in the bokeh docs
            try:
                palette = bokeh.palettes.Colorblind[len(regions)]
            except KeyError:
                palette = bokeh.palettes.TolRainbow[len(regions)]

        colormap = {r: c for r, c in zip(regions, palette)}

    footprint_regions = {}
    for region_name, loop_id in set(footprint_polygons.index.values.tolist()):
        if region_name not in footprint_regions:
            footprint_regions[region_name] = {}
        footprint_regions[region_name][loop_id] = (
            footprint_polygons.loc[(region_name, loop_id), ["RA", "decl"]]
            .apply(tuple, axis="columns")
            .tolist()
        )

    for spheremap in spheremaps:
        for region_name in footprint_regions:
            if region_name == outside:
                continue
            for this_loop in footprint_regions[region_name].values():
                loop_ds = bokeh.models.ColumnDataSource({"coords": this_loop})
                if filled:
                    spheremap.plot.patch(
                        spheremap.x_transform("coords"),
                        spheremap.y_transform("coords"),
                        color=colormap[region_name],
                        source=loop_ds,
                        **line_kwargs,
                    )
                else:
                    spheremap.plot.line(
                        spheremap.x_transform("coords"),
                        spheremap.y_transform("coords"),
                        color=colormap[region_name],
                        source=loop_ds,
                        **line_kwargs,
                    )
                spheremap.connect_controls(loop_ds)

    return spheremaps
