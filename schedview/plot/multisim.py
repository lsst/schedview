from collections import namedtuple
from math import ceil
from typing import List

import bokeh
import bokeh.core.enums
import bokeh.models
import colorcet

SimIndicators = namedtuple("SimIndicators", ("color_mapper", "color_dict", "marker_mapper", "hatch_dict"))


def generate_sim_indicators(sim_labels: List[str]):
    """Generate a tuple of simulation indicators for bokeh.

    Parameters
    ----------
    sim_labels: `list` [`str`]
        A list of simulation labels.

    Returns
    -------
    sim_indicators: `SimIndicators`
        A named tuple with:

        ``color_mapper``
            The bokeh color mapper to map sim labels to colors.
        ``color_dict``
            A python dictionary representing the same mapping as
            ``color_mapper``, above.
        ``marker_mapper``
            The bokeh mapper to map sim labels to bokeh markers.
        ``hatch_dict``
            A python dict to map sim labels to bokeh hatch styles.
    """
    num_sims = len(sim_labels)
    factors = sim_labels

    all_colors = colorcet.palette["glasbey"]
    # If there are more factors than colors, repeat colors.
    if len(factors) > len(all_colors):
        all_colors = all_colors * int(ceil(len(factors) / len(all_colors)))

    palette = colorcet.palette["glasbey"][:num_sims]
    color_mapper = bokeh.models.CategoricalColorMapper(factors=factors, palette=palette, name="simulation")

    color_dict = dict(zip(factors, palette))

    # Some bokeh symbols have the same outer shape but different inner
    # markings, but these are harder to distinguish, so put them at the end.
    all_markers = [m for m in bokeh.core.enums.MarkerType if "_" not in m] + [
        m for m in bokeh.core.enums.MarkerType if "_" in m
    ]
    # dot is hard to see
    all_markers.remove("dot")
    # If there are more factors than markers, repeat markers.
    if len(factors) > len(all_markers):
        all_markers = all_markers * int(ceil(len(factors) / len(all_markers)))

    marker_mapper = bokeh.models.CategoricalMarkerMapper(
        factors=factors,
        markers=all_markers[:num_sims],
        name="simulation",
    )

    all_hatches = tuple(bokeh.core.enums.HatchPattern)[1:]
    # If there are more factors than hatch patterns, repeat hatch patterns.
    if len(factors) > len(all_hatches):
        all_hatches = all_hatches * int(ceil(len(factors) / len(all_hatches)))

    sim_hatch_dict = dict(zip(factors, all_hatches[: len(factors)]))

    return SimIndicators(color_mapper, color_dict, marker_mapper, sim_hatch_dict)
