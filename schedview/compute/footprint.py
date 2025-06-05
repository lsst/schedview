import healpy as hp
import pandas as pd
import numpy as np
import warnings


def _build_lines(edges):
    # Do not modify the passed in DataFrame.
    edges = edges.copy()
    lowest_vertex = pd.concat([edges.lower_vertex, edges.higher_vertex]).min()
    edges["unused"] = True
    lines = []
    line_vertexes = [lowest_vertex]
    while True:
        edge_mask = np.logical_and(edges.unused, edges.lower_vertex == line_vertexes[-1])
        if np.any(edge_mask):
            next_vertex_column = "higher_vertex"
        else:
            edge_mask = np.logical_and(edges.unused, edges.higher_vertex == line_vertexes[-1])
            next_vertex_column = "lower_vertex"

        if not np.any(edge_mask):
            # We've reached the end of this line
            # Can this line connect with the start of another one?
            lines.append(line_vertexes)
            if np.any(edges.unused):
                lowest_vertex = pd.concat(
                    [edges.loc[edges.unused, "lower_vertex"], edges.loc[edges.unused, "higher_vertex"]]
                ).min()
                line_vertexes = [lowest_vertex]
                continue
            else:
                break

        available_edges = edges.loc[edge_mask, :]
        next_edge_index = available_edges.index[0]
        next_edge = available_edges.iloc[0, :]
        next_vertex = available_edges.loc[next_edge_index, next_vertex_column]
        line_vertexes.append(next_vertex)
        edges.loc[next_edge_index, "unused"] = False
    return lines


def _vertex_angle(vertex1, vertex2, unique_vertexes):
    x1, y1, z1 = unique_vertexes.loc[vertex1, ["x", "y", "z"]]
    x2, y2, z2 = unique_vertexes.loc[vertex2, ["x", "y", "z"]]
    linear_distance = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
    angle = np.degrees(2 * np.arcsin(linear_distance / 2))
    return angle


def _separate_loops(lines, loops, tolerance=0.0, unique_vertexes=None):
    for line_index, line in enumerate(lines):
        if line[0] == line[-1]:
            loops.append(line)
            del lines[line_index]
        elif unique_vertexes is not None and _vertex_angle(line[0], line[-1], unique_vertexes) < tolerance:
            # If we're close, just call it a match.
            line.append(line[0])
            loops.append(line)
            del lines[line_index]


def _join_lines(lines, tolerance=0.0, unique_vertexes=None):
    done = False

    def join_lines_once(lines, tolerance=0.0, unique_vertexes=None):
        for line1_idx, line1 in enumerate(lines[:-1]):
            for line2_idx, line2 in enumerate(lines[line1_idx + 1 :]):
                if line1[0] == line2[0]:
                    line2[0:0] = list(reversed(line1[1:]))
                    del lines[line1_idx]
                    return True
                if line1[0] == line2[-1]:
                    line2.extend(line1[1:])
                    del lines[line1_idx]
                    return True
                if line1[-1] == line2[0]:
                    line1.extend(line2[1:])
                    del lines[line2_idx]
                    return True
                if line1[-1] == line2[-1]:
                    line1.extend(list(reversed(line2)[1:]))
                    del lines[line2_idx]
                    return True

                if tolerance > 0 and unique_vertexes is not None:
                    if _vertex_angle(line1[0], line2[0], unique_vertexes) < tolerance:
                        line2[0:0] = list(reversed(line1))
                        del lines[line1_idx]
                        return True
                    if _vertex_angle(line1[0], line2[-1], unique_vertexes) < tolerance:
                        line2.extend(line1)
                        del lines[line1_idx]
                        return True
                    if _vertex_angle(line1[-1], line2[0], unique_vertexes) < tolerance:
                        line1.extend(line2)
                        del lines[line2_idx]
                        return True
                    if (
                        line1[-1] == line2[-1]
                        or _vertex_angle(line1[-1], line2[-1], unique_vertexes) < tolerance
                    ):
                        line1.extend(list(reversed(line2)))
                        del lines[line2_idx]
                        return True

        return False

    while not done:
        done = not join_lines_once(lines, tolerance, unique_vertexes)


def find_healpix_area_polygons(healpix_map, region_value=None):
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
        .stack(level="pix_vertex", future_stack=True)
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

    # Separate the edges into distinct dataframes stored in a dictionary
    region_edges = {}
    for region_name in np.unique(healpix_map):
        edge_mask = np.logical_or(
            map_edges.region_lower == region_name, map_edges.region_higher == region_name
        )
        region_edges[region_name] = map_edges.loc[edge_mask, :]

    region_loops = {}
    for region_name in region_edges:
        lines = _build_lines(region_edges[region_name])
        loops = []

        # By itself, _build_lines connects edge segments into lines, but
        # not fully connected. So, we need to go through and paste them
        # together.

        for tolerance in (0, hp.max_pixrad(nside, degrees=True), 1, 2, 4, 5, 6):
            for num_iterations in range(100):
                nlines = len(lines)
                nloops = len(loops)
                # Merge lines that can be connected by their ends
                _join_lines(lines, tolerance=tolerance, unique_vertexes=unique_vertexes)

                # Identify any lines that end at their beginning, and declare them
                # done by adding them to loops and taking them out of lines.
                _separate_loops(lines, loops, tolerance=tolerance, unique_vertexes=unique_vertexes)

                # If nothing has changed, we've done all we can do
                # (at this tolerance)
                stabilized = len(lines) == nlines and len(loops) == nloops
                if stabilized:
                    break

        if not stabilized:
            warnings.warn("Loop finding could not stabilize")
        region_loops[region_name] = loops

    # Convert to a pandas.DataFrame indexed by region and loop index
    loop_dfs = []
    for region_name in region_loops:
        if region_name == "":
            continue
        for i, loop in enumerate(region_loops[region_name]):
            this_loop_df = unique_vertexes.loc[loop, ["RA", "decl", "x", "y", "z"]]
            this_loop_df.loc[:, ["region", "loop"]] = region_name, i
            loop_dfs.append(this_loop_df)
    region_loop_df = pd.concat(loop_dfs).reset_index(drop=True).set_index(["region", "loop"])

    return region_loop_df
