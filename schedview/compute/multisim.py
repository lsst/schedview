import pandas as pd


def often_repeated_fields(visits: pd.DataFrame, min_counts: int = 4):
    field_repeats = visits.groupby(["fieldRA", "fieldDec", "filter", "sim_index"]).agg(
        {"start_date": ["count", "min", "max"], "label": "first"}
    )
    column_map = {
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

    often_repeated_field_stats = (
        field_repeats.reset_index("sim_index")
        .loc[often_repeated_fields, :]
        .set_index("sim_index", append=True)
    )
    return often_repeated_fields, often_repeated_field_stats
