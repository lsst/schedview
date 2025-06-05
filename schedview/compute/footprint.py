import healpy as hp
import pandas as pd
import numpy as np


def find_healpix_area_edges(healpix_map, region_value=None):
    npix = healpix_map.shape[0]
    nside = hp.npix2nside(npix)
    hpids = np.arange(npix)

    # Get vertexes of each healpixel
    vertexes = (
        pd.DataFrame(
            hp.boundaries(nside, hpids).reshape(npix, 12),
            index=pd.Index(hpids, name="hpid"),
            columns=pd.MultiIndex.from_product(
                [["x", "y", "z"], [0, 1, 2, 3]], names=("coordinate", "pix_vertex")
            ),
        )
        .swaplevel(0, 1, axis="columns")
        .sort_index(axis="columns")
        .stack(level="pix_vertex")
    )

    # Number unique vertexes, so vertexes from seporate healpixels
    # can be matched on one column for simplicity.
    # Include column matching the unique vertex number to the coordinate
    # values we might want.
    unique_vertexes = vertexes.assign(n=1).groupby(["x", "y", "z"]).sum().reset_index()
    unique_vertexes.index.name = "vertex_id"
    lonlat = hp.vec2ang(unique_vertexes.loc[:, ["x", "y", "z"]].values, lonlat=True)
    unique_vertexes["RA"] = lonlat[0]
    unique_vertexes["decl"] = lonlat[1]
    unique_vertexes["eq_coords"] = unique_vertexes[["RA", "decl"]].apply(tuple, axis="columns")

    # Include vertex ids in our DataFrame of vertexes
    vec2vertex = unique_vertexes.reset_index().set_index(["x", "y", "z"])["vertex_id"]
    vertexes = (
        vertexes.reset_index()
        .set_index(["x", "y", "z"])
        .assign(vertex_id=vec2vertex)
        .reset_index()
        .set_index(["hpid", "pix_vertex"])
    )

    # Find the edges of each healpixel, where an edge is a segment from
    # consecutive vertexes of that healpixel.
    raw_edges = (
        vertexes.reset_index("pix_vertex")
        .join(vertexes.reset_index("pix_vertex"), on="hpid", lsuffix="_start", rsuffix="_end")
        .query("(pix_vertex_end == pix_vertex_start + 1) or (pix_vertex_start==3 and pix_vertex_end==0)")
        .loc[:, ["vertex_id_start", "vertex_id_end"]]
        .rename(columns={"vertex_id_start": "start_vertex", "vertex_id_end": "end_vertex"})
    )
    raw_edges.columns.name = ""

    # Put the direction of the edges in vertex index order, so edges of
    # different healpixels will match even though they are in a different
    # order around the healpixels.
    start_higher_edges = raw_edges.start_vertex > raw_edges.end_vertex
    edges = pd.DataFrame(
        {
            "lower_vertex": np.where(start_higher_edges, raw_edges.end_vertex, raw_edges.start_vertex),
            "higher_vertex": np.where(start_higher_edges, raw_edges.start_vertex, raw_edges.end_vertex),
            "hpid": raw_edges.index.values,
        },
    )

    # Get the neighbors of each healpixel
    neighbors = pd.DataFrame(
        hp.get_all_neighbours(nside, hpids), index=["SW", "W", "NW", "N", "NE", "E", "SE", "S"], columns=hpids
    ).T.stack()
    neighbors = neighbors.reset_index(0)
    neighbors.columns = ["lower_hpid", "higher_hpid"]
    neighbors = neighbors.query("higher_hpid > lower_hpid")
    neighbors.columns = pd.MultiIndex.from_product([["lower_hpix", "higher_hpix"], ["hpid"]])

    # Find all edges present in multiple healpixels.
    matched_edges = edges.merge(
        edges,
        left_on=["lower_vertex", "higher_vertex"],
        right_on=["lower_vertex", "higher_vertex"],
        how="inner",
        suffixes=["_lower", "_higher"],
    )
    # Make sure healpixels are in a well determined order.
    matched_edges = (
        matched_edges.loc[matched_edges.hpid_lower < matched_edges.hpid_higher, :]
        .set_index(["hpid_lower", "hpid_higher"])
        .loc[:, ["lower_vertex", "higher_vertex"]]
    )

    # Add the healpixel values for the healpixels on each side of each edge..
    matched_edges["region_lower"] = healpix_map[matched_edges.index.get_level_values("hpid_lower")]
    matched_edges["region_higher"] = healpix_map[matched_edges.index.get_level_values("hpid_higher")]
    matched_edges.columns.name = ""

    # Select edges where the healpixel values are different on each side
    # of the edge.
    map_edges = matched_edges.loc[matched_edges.region_lower != matched_edges.region_higher].copy()

    # Replace the vertex ids with equatorial coordinates
    map_edges["start_coords"] = unique_vertexes.loc[map_edges["lower_vertex"].values, "eq_coords"].values
    map_edges["end_coords"] = unique_vertexes.loc[map_edges["higher_vertex"].values, "eq_coords"].values
    map_edges.drop(columns=["lower_vertex", "higher_vertex"])

    requested_edge_mask = (
        np.full(len(map_edges), True, dtype=bool)
        if region_value is None
        else np.logical_or(map_edges.region_lower == region_value, map_edges.region_higher == region_value)
    )
    requested_edges = map_edges.loc[requested_edge_mask, :]

    return requested_edges
