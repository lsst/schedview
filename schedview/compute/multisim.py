import itertools
import math
from typing import Hashable

import numpy as np
import pandas as pd


def often_repeated_fields(visits: pd.DataFrame, min_counts: int = 4):
    """Find often repeated fields in a table of visits.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The visits as a DataFrame with the following columns:

        ``fieldRA``
            R.A. in degrees.
        ``fieldDec``
            Declination in degrees.
        ``filter``
            The filter.
        ``sim_index``
            An ``int`` identifying which simulation a visit came from.
        ``start_date``
            The starting ``datetime64[ns, UTC]`` for the visit.
        ``label``
            The ``str`` label for the simulation.
    min_counts : `int`
        The minimum visits in a single simulation a field must have to be
        considererd "often visited".

    Returns
    -------
    often_repeated_fields: `pandas.DataFrame`
        The table of repeated field parameters, with the following columns:

        ``fieldRA``
            R.A. in degrees.
        ``fieldDec``
            Declination in degrees.
        ``filter``
            The filter.
    often_repeated_field_stats: `pandas.DataFrame`
        Statistics on the repetitions of each field.
        The index is a ``pandas.MultiIndex`` with the following levels:

        ``fieldRA``
            R.A. in degrees.
        ``fieldDec``
            Declination in degrees.
        ``filter``
            The filter.
        ``sim_index``
            An ``int`` identifying which simulation a visit came from.

        The columns are:

        ``count``
            The (``int``) number of visits in the simulation on the field.
        ``first_time``
            The ``datetime64[ns, UTC]`` start time of the first visit to the
            field in the simulation.
        ``last_time``
            The ``datetime64[ns, UTC]`` start time of the last visit to the
            field in the simulation.
        ``label``
            The ``str`` label for the simulation.
    """
    field_repeats: pd.DataFrame = visits.groupby(["fieldRA", "fieldDec", "filter", "sim_index"]).agg(
        {"start_date": ["count", "min", "max"], "label": "first"}
    )
    column_map: dict[tuple[str, str], str] = {
        ("start_date", "count"): "count",
        ("start_date", "min"): "first_time",
        ("start_date", "max"): "last_time",
        ("label", "first"): "label",
    }
    field_repeats.columns = pd.Index([column_map[c] for c in field_repeats.columns])

    # Get the index in ra/dec/filter then use that as in index so we can show
    # instances in simulations that have fewer than four visits of a field the
    # is often visited in another simulation.
    often_repeated_fields = (
        field_repeats.query(f"count >= {min_counts}").droplevel("sim_index", "index").index.unique()
    )

    often_repeated_field_stats: pd.DataFrame = (
        field_repeats.reset_index("sim_index")
        .loc[often_repeated_fields, :]
        .set_index("sim_index", append=True)
    )
    return often_repeated_fields.to_frame(), often_repeated_field_stats


def count_visits_by_sim(
    visits: pd.DataFrame,
    sim_identifier_column: str = "sim_index",
    visit_spec_columns: tuple[str] = ("fieldRA", "fieldDec", "filter", "visitExposureTime"),
) -> pd.DataFrame:
    """Count the numbers of visits on each field in each simulation.

    Parameters
    ----------
    visits : `pd.DataFrame`
        A table that must include both the columns listed in
        ``sim_identifier_column`` and ``visit_spec_columns`` (below).
    sim_identifier_column : `str`, optional
        A column that uniquely identifies visits, by default "sim_index"
    visit_spec_columns : `tuple`[`str`], optional
        Columns that, together, uniquely identify a field that can be visited,
        by default ("fieldRA", "fieldDec", "filter", "visitExposureTime")

    Returns
    -------
    visit_counts : `pd.DataFrame`
        A table in which columns listed in the ``visit_spec_columns``
        constitute levels of the `pd.MultiIndex`, and each unique value of
        the column listed in ``sim_identifier_column`` has a column named
        after it. The values are the numbers of visits in the corresponding
        combination of visit parameters in identified simulation.
    """

    visit_counts = (
        visits.groupby([sim_identifier_column] + list(visit_spec_columns))
        .count()
        .iloc[:, 0]
        .rename("count")
        .reset_index()
        .pivot(index=list(visit_spec_columns), columns=[sim_identifier_column], values="count")
        .fillna(0)
        .astype(int)
    )
    return visit_counts


def fraction_common(visit_counts: pd.DataFrame, sim1: Hashable, sim2: Hashable, match_count: bool = True):
    """_summary_

    Parameters
    ----------
    visit_counts : `pd.DataFrame`
        A table of the number of counts of field in each simulation.
        Each row corresponds to a field, and the table must includes
        columns with the names set by the ``sim1`` and ``sim2`` parameters
        below. Values are integers.
    sim1 : `Hashable`
        The name of the column with the counts for the reference simulation.
    sim2 : `Hashable`
        The name of the column with the counts for the comparison simulation.
    match_count : `bool`, optional
        Match "one to one" between fields. For example, if sim1 has 4 visits
        on a field and sim2 has 11, then if match_count is True, then sim1 will
        be reported as having 4 matches with sim2, and sim2 as 4 matches with
        sim1. But, if match_count is False, then sim1 will still be reported as
        having 4 matches with sim2, but sim2 will be reported as having 11
        matches with sim1.
        By default True

    Returns
    -------
    fraction_common: `float`
        The fraction of visits in sim2 that it has in common with sim1.
    """
    # Only count fields for which there is at least one visit in sim1
    these_visit_counts = visit_counts[visit_counts[sim2] > 0]

    if not match_count:
        # Count any number of repetitons of a field only once
        for sim in sim1, sim2:
            these_visit_counts.loc[these_visit_counts[sim] > 0, sim] = 1

    num_common_visits = these_visit_counts[[sim2, sim1]].min(axis="columns").sum()
    num_visits2 = these_visit_counts[sim2].sum()
    fraction_common = num_common_visits / num_visits2
    return fraction_common


def make_fraction_common_matrix(visit_counts, match_count=True, sim_indexes=None):
    if sim_indexes is None:
        sim_indexes = visit_counts.columns.values

    common_matrix = pd.DataFrame(np.nan, index=sim_indexes, columns=sim_indexes)
    for row in sim_indexes:
        for column in sim_indexes:
            common_matrix.loc[row, column] = fraction_common(
                visit_counts, row, column, match_count=match_count
            )
    return common_matrix


def match_visits_across_sims(start_times, sim_indexes=(1, 2), max_match_dist=np.inf):
    for sim_index in sim_indexes:
        if sim_index not in start_times.index:
            return pd.DataFrame({sim_indexes[0]: [], sim_indexes[1]: [], "delta": []})

    if len(start_times.loc[[sim_indexes[0]]]) >= len(start_times.loc[[sim_indexes[1]]]):
        sim_map = {"longer": sim_indexes[0], "shorter": sim_indexes[1]}
    else:
        sim_map = {"longer": sim_indexes[1], "shorter": sim_indexes[0]}

    longer = start_times.loc[[sim_map["longer"]]]
    shorter = start_times.loc[[sim_map["shorter"]]]

    num_combinations = math.comb(len(longer), len(shorter))
    if num_combinations > 1000:
        # There are too many combinations to do a complete search in reasonable
        # time so assume the matches are sequential.
        def make_seq_iter(num_offsets, sequence_length):
            for i in range(num_offsets):
                yield np.arange(sequence_length) + i

        combo_iterator = make_seq_iter(len(longer) - len(shorter), len(shorter))
    else:
        combo_iterator = itertools.combinations(np.arange(len(longer)), len(shorter))

    matches = pd.DataFrame({"longer": longer.values[: len(shorter)], "shorter": shorter.values})
    best_diff = np.inf
    most_matches = 0
    best_match = None
    for matched_ids in combo_iterator:
        matches.loc[:, "longer"] = longer.values[np.array(matched_ids)]
        matches["delta"] = (matches.shorter - matches.longer).dt.total_seconds()
        good_matches = matches.query(f"abs(delta) < {max_match_dist}")
        num_matches = len(good_matches)
        max_diff = matches["delta"].max()
        if (num_matches >= most_matches) and (max_diff < best_diff):
            best_match = good_matches.copy().rename(columns=sim_map)
            best_diff = max_diff
            most_matches = num_matches

    return best_match


def compute_matched_visit_delta_statistics(
    visits,
    sim_identifier_reference_value=1,
    sim_identifier_column="sim_index",
    visit_spec_columns=("fieldRA", "fieldDec", "filter", "visitExposureTime"),
):
    delta_stats_list = []

    def _compute_best_match_delta_stats(
        these_visits, sim_identifier_values, sim_identifier_column="sim_index"
    ):
        return (
            match_visits_across_sims(
                these_visits.set_index(sim_identifier_column).start_date, sim_identifier_values
            )
            .loc[:, "delta"]
            .describe()
        )

    for sim_identifier_comparison_value in visits[sim_identifier_column].unique():
        if sim_identifier_comparison_value == sim_identifier_reference_value:
            continue
        sim_identifier_values = [sim_identifier_reference_value, sim_identifier_comparison_value]
        these_delta_stats = (
            visits.groupby(list(visit_spec_columns))
            .apply(
                _compute_best_match_delta_stats,
                sim_identifier_values=sim_identifier_values,
                sim_identifier_column=sim_identifier_column,
            )
            .query("count > 0")
        )
        these_delta_stats[sim_identifier_column] = sim_identifier_comparison_value
        delta_stats_list.append(these_delta_stats)

    matched_visit_delta_stats = (
        pd.concat(delta_stats_list).set_index(sim_identifier_column, append=True).sort_index()
    )
    return matched_visit_delta_stats
