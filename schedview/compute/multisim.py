import numpy as np
import pandas as pd


def compute_offsets(first_index, second_index, df):
    cols = ["observationId", "sim_index", "observationStartMJD"]
    first_df = df.loc[df.sim_index == first_index, cols].sort_values("observationStartMJD")
    second_df = df.loc[df.sim_index == second_index, cols].sort_values("observationStartMJD")

    if len(first_df) == 0 and len(second_df) == 0:
        columns = [
            f"observationId_{first_index}",
            f"observationId_{second_index}",
            f"revisit_id_{first_index}",
            f"revisit_id_{second_index}",
            f"sim_index_{first_index}",
            f"sim_index_{second_index}",
            f"observationStartMJD_{first_index}",
            f"observationStartMJD_{second_index}",
            "mjd_diff",
        ]
        result = pd.DataFrame(columns=columns)
        result = None
    elif len(first_df) == 0 or len(second_df) == 0:
        if len(first_df) == 0:
            empty_index, content_index = first_index, second_index
            content_df = second_df
        else:
            empty_index, content_index = second_index, first_index
            content_df = first_df

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
    elif len(first_df) == len(second_df):
        first_df["revisit_id"] = np.arange(len(first_df))
        second_df["revisit_id"] = np.arange(len(first_df))
        suffixes = [f"_{first_index}", f"_{second_index}"]
        result = first_df.merge(second_df, how="left", on="revisit_id", suffixes=suffixes)
        result["mjd_diff"] = (
            result["observationStartMJD" + suffixes[0]] - result["observationStartMJD" + suffixes[1]]
        )
    else:
        if len(first_df) > len(second_df):
            longer_index, shorter_index = first_index, second_index
            longer_df, shorter_df = first_df, second_df
        else:
            longer_index, shorter_index = second_index, first_index
            longer_df, shorter_df = second_df, first_df

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
