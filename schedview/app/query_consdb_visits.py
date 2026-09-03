import argparse
from pathlib import Path

from schedview import DayObs
from schedview.collect.visits import NIGHT_STACKERS, read_visits

TELESCOPE_MAP = {
    "simonyi": "lsstcam",
    "auxtel": "latiss",
}


NUM_NIGHTS = 1


def _clean_visits_for_parquet(visits):
    """Clean a visits DataFrame for writing to parquet.

    Converts all-NaN object columns to float and fills NaN values
    in string columns with empty strings, so that parquet can infer
    concrete column types.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The visits DataFrame to clean.

    Returns
    -------
    cleaned : `pandas.DataFrame`
        A cleaned copy of the input DataFrame.
    """
    cleaned_visits = visits.copy()

    all_nan_obj_cols = [
        c
        for c in cleaned_visits.columns
        if cleaned_visits[c].dtype == object and cleaned_visits[c].isna().all()
    ]
    for col in all_nan_obj_cols:
        cleaned_visits[col] = cleaned_visits[col].astype(float)

    def is_string(value):
        return isinstance(value, str)

    string_columns = [
        c
        for c in cleaned_visits.select_dtypes(include="object").columns
        if cleaned_visits[c].dropna().map(is_string).all()
    ]

    cleaned_visits[string_columns] = cleaned_visits[string_columns].fillna("")

    return cleaned_visits


def query_consdb_visits_cli():
    """Query consdb for visits and write to a parquet file."""
    parser = argparse.ArgumentParser(
        prog="query_consdb_visits",
        description="Query consdb for visits on a given night and write to parquet.",
    )
    parser.add_argument(
        "dayobs",
        type=str,
        help="The day of observation in YYYYMMDD format.",
    )
    parser.add_argument(
        "telescope",
        type=str,
        choices=list(TELESCOPE_MAP.keys()),
        help="The telescope: simonyi or auxtel.",
    )
    parser.add_argument(
        "dir",
        type=str,
        help="Output directory for the parquet file.",
    )
    parser.add_argument(
        "--nights",
        type=int,
        default=1,
        help="Number of nights to query.",
    )

    args = parser.parse_args()

    visit_source = TELESCOPE_MAP[args.telescope]

    visits = read_visits(
        args.dayobs,
        visit_source,
        NIGHT_STACKERS,
        num_nights=args.nights,
    )

    # If the reader of the parquet file can use the index
    # make it the visit_id so that it is meaningful, but
    # also make sure the visit_id column is there
    # so that readers that do not read the axis can have
    # access to it.
    # Take the name off of the index so there will not be
    # name ambiguity in pandas.
    if "visit_id" in visits.columns:
        visits = visits.set_index("visit_id", drop=False).rename_axis(index=None)

    if "index" in visits.columns:
        del visits["index"]

    cleaned_visits = _clean_visits_for_parquet(visits)

    day_obs_obj = DayObs.from_date(args.dayobs)
    iso_date = day_obs_obj.date.isoformat()
    output_dir = Path(args.dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{iso_date}.parquet"
    cleaned_visits.to_parquet(output_path, index=True)


if __name__ == "__main__":
    query_consdb_visits_cli()
