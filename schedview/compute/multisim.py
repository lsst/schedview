from functools import partial

import numpy as np
import pandas as pd


def compute_offsets(sim_indexes, visits):
    cols = ["observationId", "sim_index", "observationStartMJD"]
    sim_visits = [
        visits.loc[visits.sim_index == sim_indexes[0], cols].sort_values("observationStartMJD"),
        visits.loc[visits.sim_index == sim_indexes[1], cols].sort_values("observationStartMJD"),
    ]

    if len(sim_visits[0]) == 0 and len(sim_visits[1]) == 0:
        columns = [
            f"observationId_{sim_indexes[0]}",
            f"observationId_{sim_indexes[1]}",
            f"revisit_id_{sim_indexes[0]}",
            f"revisit_id_{sim_indexes[1]}",
            f"sim_index_{sim_indexes[0]}",
            f"sim_index_{sim_indexes[1]}",
            f"observationStartMJD_{sim_indexes[0]}",
            f"observationStartMJD_{sim_indexes[1]}",
            "mjd_diff",
        ]
        result = pd.DataFrame(columns=columns)
        result = None
    elif len(sim_visits[0]) == 0 or len(sim_visits[1]) == 0:
        if len(sim_visits[0]) == 0:
            empty_index, content_index = sim_indexes[0], sim_indexes[1]
            content_df = sim_visits[1]
        else:
            empty_index, content_index = sim_indexes[1], sim_indexes[0]
            content_df = sim_visits[0]

        result = pd.DataFrame(
            {
                f"observationId_{content_index}": content_df["observationId"],
                f"observationId_{empty_index}": np.nan,
                f"revisit_id_{content_index}": np.arange(len(content_df)),
                f"revisit_id_{empty_index}": np.nan,
                f"sim_index_{content_index}": content_index,
                f"sim_index_{empty_index}": empty_index,
                f"observationStartMJD_{content_index}": content_df["observationStartMJD"],
                f"observationStartMJD_{empty_index}": np.nan,
                "mjd_diff": np.nan,
            }
        )
    elif len(sim_visits[0]) == len(sim_visits[1]):
        sim_visits[0]["revisit_id"] = np.arange(len(sim_visits[0]))
        sim_visits[1]["revisit_id"] = np.arange(len(sim_visits[1]))
        suffixes = [f"_{sim_indexes[0]}", f"_{sim_indexes[1]}"]
        result = sim_visits[0].merge(sim_visits[1], how="left", on="revisit_id", suffixes=suffixes)
        result["mjd_diff"] = (
            result["observationStartMJD" + suffixes[0]] - result["observationStartMJD" + suffixes[1]]
        )
    else:
        if len(sim_visits[0]) > len(sim_visits[1]):
            longer_index, shorter_index = sim_indexes[0], sim_indexes[1]
            longer_df, shorter_df = sim_visits[0], sim_visits[1]
        else:
            longer_index, shorter_index = sim_indexes[1], sim_indexes[0]
            longer_df, shorter_df = sim_visits[1], sim_visits[0]

        suffixes = [f"_{longer_index}", f"_{shorter_index}"]
        unmatched_visits = len(longer_df) - len(shorter_df)
        min_diff = np.inf
        longer_df["revisit_id"] = np.arange(len(longer_df))
        for offset in range(unmatched_visits + 1):
            shorter_df["revisit_id"] = np.arange(len(shorter_df)) + offset
            candidate_result = longer_df.merge(shorter_df, how="left", on="revisit_id", suffixes=suffixes)
            candidate_result["mjd_diff"] = (
                candidate_result["observationStartMJD" + suffixes[0]]
                - candidate_result["observationStartMJD" + suffixes[1]]
            )
            this_diff = np.max(np.abs(candidate_result.mjd_diff))
            if this_diff < min_diff:
                result = candidate_result

    return result


def _mean_angle(angles):
    # We can't just take the mean of angles because of wrapping issues:
    # the mean of 1 and 359 should be 0, not 180.
    # So, take the mean position on the x/y plane instead.
    ang_rad = np.radians(angles)
    mean_sin = np.mean(np.sin(ang_rad))
    mean_cos = np.mean(np.cos(ang_rad))
    mean_angle = np.degrees(np.arctan2(mean_sin, mean_cos))
    return mean_angle


def _count_diff_in_num_of_visits(sim_indexes, visits):
    counted_visits = visits.sim_index.value_counts()

    # Not all of our indexes are guaranteed to have visits, in which
    # case the index will not be present at all in the counted_visits
    # Series. Make sure they are, and are 0.
    sim_counts = pd.Series({i: 0 for i in sim_indexes})
    sim_counts[counted_visits.index] = counted_visits

    # We'll need a rotSkyPos to plot, even though we don't match on it,
    # because they aren't all the same for the same pointing.
    rot_sky_pos = _mean_angle(visits.rotSkyPos)

    result = pd.Series(
        {
            "rotSkyPos": rot_sky_pos,
            "diff_nums": sim_counts[sim_indexes[0]] - sim_counts[sim_indexes[1]],
            "most_nums": sim_counts.max(),
            f"num_{sim_indexes[0]}": sim_counts[sim_indexes[0]],
            f"num_{sim_indexes[1]}": sim_counts[sim_indexes[1]],
        }
    )
    return result


def count_diff_in_num_of_visits_by_pointing(sim_indexes, visits):
    visit_nums = (
        visits.groupby(["filter", "fieldRA", "fieldDec"])
        .apply(partial(_count_diff_in_num_of_visits, sim_indexes))
        .reset_index(["fieldRA", "fieldDec"])
    )
    return visit_nums
