import itertools
import math

import healpy as hp
import numpy as np
import pandas as pd

from schedview import band_column


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
        ``start_timestamp``
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

    Notes
    -----
    This created table is intended to provide overviews of sets of visits
    to specific fields for which the specific pointing and filter combinations
    are of particular interest (e.g. DDF fields).
    """
    field_repeats: pd.DataFrame = visits.groupby(
        ["fieldRA", "fieldDec", band_column(visits), "sim_index"]
    ).agg({"start_timestamp": ["count", "min", "max"], "label": "first"})
    column_map: dict[tuple[str, str], str] = {
        ("start_timestamp", "count"): "count",
        ("start_timestamp", "min"): "first_time",
        ("start_timestamp", "max"): "last_time",
        ("label", "first"): "label",
    }
    # type hinting doesn't recognize that the column names in a multiindex
    # are tuples.
    field_repeats.columns = pd.Index([column_map[c] for c in field_repeats.columns])  # type: ignore

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
    visit_spec_columns: tuple = ("fieldHpid", "band", "visitExposureTime"),
    nside: int = 2**18,
) -> pd.DataFrame:
    """Count the numbers of visits on each field in each simulation.

    Parameters
    ----------
    visits : `pd.DataFrame`
        A table that must include both the columns listed in
        ``sim_identifier_column`` and ``visit_spec_columns`` (below).
        This ``DataFrame`` should include visits from all simulations to
        be compared, with a column that identifies which simulation each
        visits was from (sepecified by ``sim_identifier_column``).
    sim_identifier_column : `str`, optional
        A column that uniquely identifies visits, by default "sim_index"
    visit_spec_columns : `tuple`[`str`], optional
        Columns that, together, uniquely identify a field that can be visited.
        If fieldHpid is included but not a column, and fieldRA and fieldDec
        are, it will be computed on the fly.
        by default ("fieldHpid", "band", "visitExposureTime").
    nside : `int`
        nside to use if fieldHpid is to be computed on the fly.

    Returns
    -------
    visit_counts : `pd.DataFrame`
        A table in which columns listed in the ``visit_spec_columns``
        constitute levels of the `pd.MultiIndex`, and each unique value of
        the column listed in ``sim_identifier_column`` has a column named
        after it. The values are the numbers of visits in the corresponding
        combination of visit parameters in identified simulation.
    """

    # If we asked for band and it isn't there, fall back on filter
    if "band" in visit_spec_columns and "band" not in visits.columns:
        visit_spec_columns = tuple("filter" if c == "band" else c for c in visit_spec_columns)

    if "filter" in visit_spec_columns and "filter" not in visits.columns:
        visit_spec_columns = tuple("band" if c == "filter" else c for c in visit_spec_columns)

    if "fieldHpid" in visit_spec_columns and "fieldHpid" not in visits.columns:
        visits = visits.copy()
        hpid = hp.ang2pix(nside, visits.fieldRA, visits.fieldDec, lonlat=True)
        ra, decl = hp.pix2ang(nside, hpid, lonlat=True)
        visits["hp_ra"] = ra
        visits["hp_decl"] = decl
        visit_spec_columns = tuple(c for c in visit_spec_columns if c != "fieldHpid") + ("hp_ra", "hp_decl")

    grouping_columns = [sim_identifier_column] + list(visit_spec_columns)

    visit_counts = (
        visits.groupby(grouping_columns)
        .count()
        .loc[:, "start_timestamp"]
        .rename("count")
        .reset_index()
        .pivot(index=list(visit_spec_columns), columns=[sim_identifier_column], values="count")
        .fillna(0)
        .astype(int)
    )
    return visit_counts


def fraction_common(visit_counts: pd.DataFrame, sim1: int | str, sim2: int | str, match_count: bool = True):
    """Count the fraction of visits in simulation 2 that it has with sim 1.

    Parameters
    ----------
    visit_counts : `pd.DataFrame`
        A table of the number of counts of field in each simulation.
        Each row corresponds to a field, and the table must includes
        columns with the names set by the ``sim1`` and ``sim2`` parameters
        below. Values are integers.
    sim1 : `int` | `str`
        The name of the column with the counts for the reference simulation.
    sim2 : `int` | `str`
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
    these_visit_counts: pd.DataFrame = visit_counts.loc[visit_counts[sim2] > 0, :]

    if not match_count:
        # if we are not matching counts, visits in sim1 can match any number
        # of visits is sim2.
        present_in_sim1 = these_visit_counts.loc[:, sim1] > 0
        these_visit_counts.loc[present_in_sim1, sim1] = np.iinfo(np.int32).max

    num_common_visits = these_visit_counts[[sim2, sim1]].min(axis="columns").sum()
    num_visits2 = these_visit_counts[sim2].sum()
    fraction_common = num_common_visits / num_visits2
    return fraction_common


def make_fraction_common_matrix(
    visit_counts: pd.DataFrame, match_count: bool = True, sim_indexes: list | None = None
):
    """Create a matric showing overlap fractions between different simulations.

    Parameters
    ----------
    visit_counts : `pd.DataFrame`
        A data frame in which each row corresponds to a set of visits on a
        common field, each row to a simulation, and the value in each cell
        the number of visits to the field in each simulation.
    match_count : `bool`, optional
        Match visits "one to one" acress simulations if True, (potentialy)
        many to one if False, by default True
    sim_indexes : `list` or `None`, optional
        The list of simulations to include. Each value in the list must
        be a column name in ``visit_counts``. If ``None``, use all columns.
        By default, ``None``.

    Returns
    -------
    common_matrix : `pd.DataFrame`
        A matrix with one row and column for each value in ``sim_indexes``
        (or every column in ``visit_counts``, if ``sim_indexes`` was ``None``.)
        The value in row r, column y is the fraction of visits in simulation y
        that are also present in simulation r.
    """

    if sim_indexes is None:
        sim_indexes = list(visit_counts.columns.values)

    common_matrix = pd.DataFrame(np.nan, index=sim_indexes, columns=sim_indexes)
    for row in sim_indexes:
        for column in sim_indexes:
            common_matrix.loc[row, column] = fraction_common(
                visit_counts, row, column, match_count=match_count
            )
    return common_matrix


def match_visits_across_sims(
    start_times: pd.Series, sim_indexes: tuple[int, int] = (1, 2), max_match_dist: float = np.inf
) -> pd.DataFrame:
    """Match corresponding visits across two opsim simulations.

    Parameters
    ----------
    start_times : `pd.Series`
        A series of dtype ``datetime64[ns, UTC]`` indexed by simulation id,
        such that ``start_times.loc[1].iloc[3]`` is the start time of the
        fourth visit to a field in simulation 1.
    sim_indexes :  `tuple`[`int`], optional
        The simulations to compare, by default (1, 2)
    max_match_dist : `float`, optional
        The maximum time difference to allow for a match, in seconds,
        by default np.inf

    Returns
    -------
    best_match : `pd.DataFrame`
        A data frame with one row for each matched visits, columns named for
        each simulation index with the start times for the matched visits,
        and a column named ``delta`` with the time difference in seconds.
    """

    for sim_index in sim_indexes:
        if sim_index not in start_times.index:
            return pd.DataFrame({sim_indexes[0]: [], sim_indexes[1]: [], "delta": []})

    if len(start_times.loc[[sim_indexes[0]]]) >= len(start_times.loc[[sim_indexes[1]]]):
        sim_map = {"longer": sim_indexes[0], "shorter": sim_indexes[1]}
    else:
        sim_map = {"longer": sim_indexes[1], "shorter": sim_indexes[0]}

    longer = start_times.loc[[sim_map["longer"]]].reset_index(drop=True)
    shorter = start_times.loc[[sim_map["shorter"]]].reset_index(drop=True)

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

    # Use copy here so that the column in the dataframe can be update without
    # corrupting the origin longer Series.
    matches = pd.DataFrame({"longer": longer[: len(shorter)].copy(), "shorter": shorter.copy()})
    best_max_diff = np.inf
    # msdiff => mean squared difference
    best_msdiff = np.inf
    most_matches = 0
    best_match = None
    for matched_ids in combo_iterator:
        these_longer = longer[np.array(matched_ids)].copy()
        these_longer.index = matches.index
        matches.loc[:, "longer"] = these_longer
        matches["delta"] = (matches.shorter - matches.longer).dt.total_seconds()
        good_matches = matches.query(f"abs(delta) < {max_match_dist}")
        num_matches = len(good_matches)
        max_diff = np.abs(matches["delta"]).max()

        # msdiff => mean squared difference
        msdiff = (matches["delta"] ** 2).mean()
        if num_matches >= most_matches:
            if (max_diff < best_max_diff) or (max_diff == best_max_diff and msdiff < best_msdiff):
                best_match = good_matches.copy().rename(columns=sim_map)
                best_max_diff = max_diff
                best_msdiff = msdiff
                most_matches = num_matches

    assert best_match is not None

    return best_match


def compute_matched_visit_delta_statistics(
    visits: pd.DataFrame,
    sim_identifier_reference_value: int | str = 1,
    sim_identifier_column: str = "sim_index",
    visit_spec_columns: tuple[str, ...] = ("fieldHpid", "band", "visitExposureTime"),
    nside: int = 2**18,
) -> pd.DataFrame:
    """Compute statistics on time differencse in visits matched across sims.

    Parameters
    ----------
    visits : `pd.DataFrame`
        _description_
    sim_identifier_reference_value : `int` or `str`, optional
        Value of sim_identifier_column for the reference simulation times,
        by default 1.
    sim_identifier_column : `str`, optional
        Column that in visits that identifies simulations,
        by default "sim_index".
    visit_spec_columns : `tuple`[`str`], optional
        Columns that, together, uniquely identify a field that can be visited.
        If fieldHpid is included but not a column, and fieldRA and fieldDec
        are columns, fieldHpid will be computed on the fly.
        by default ("fieldHpid", "band", "visitExposureTime").
    nside : `int`
        nside to use if fieldHpid is to be computed on the fly.

    Returns
    -------
    matched_visit_delta_stats : `pd.DataFrame`
        Statistics for each matched field.
        The index is a `pandas.MultiIndex` with levels matching those specified
        by ``visit_spec_columns``, and there are columns for these statistics:
        ``count``, ``mean``, ``std``, ``min``, ``25%``, ``50%``, ``75%``,
        ``max``.
    """

    if "fieldHpid" in visit_spec_columns and "fieldHpid" not in visits.columns:
        visits = visits.copy()
        hpid = hp.ang2pix(nside, visits.fieldRA, visits.fieldDec, lonlat=True)
        ra, decl = hp.pix2ang(nside, hpid, lonlat=True)
        visits["hp_ra"] = ra
        visits["hp_decl"] = decl
        visit_spec_columns = tuple(c for c in visit_spec_columns if c != "fieldHpid") + ("hp_ra", "hp_decl")

    delta_stats_list = []

    def _compute_best_match_delta_stats(
        these_visits: pd.DataFrame,
        sim_identifier_values: tuple[int, int],
        sim_identifier_column: str | int = "sim_index",
    ) -> pd.Series:
        these_matches = match_visits_across_sims(
            these_visits.set_index(sim_identifier_column).start_timestamp, sim_identifier_values
        )
        return these_matches.loc[:, "delta"].describe()

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
                include_groups=False,
            )
            .query("count > 0")
        )
        these_delta_stats[sim_identifier_column] = sim_identifier_comparison_value
        delta_stats_list.append(these_delta_stats)

    matched_visit_delta_stats = (
        pd.concat(delta_stats_list).set_index(sim_identifier_column, append=True).sort_index()
    )
    return matched_visit_delta_stats
