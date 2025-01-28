import datetime

import numpy as np
from astropy.time import Time
from rubin_scheduler.site_models import SeeingModel

import schedview.compute


def add_day_obs(visits):
    """Add day_obs columns to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFRame with additonal columns: day_obs_date,
        day_obs_mjd, and day_obs_iso8601.
    """
    day_obs_mjd = np.floor(visits["observationStartMJD"] - 0.5).astype("int")
    day_obs_datetime = Time(day_obs_mjd, format="mjd").datetime
    day_obs_date = [datetime.date(t.year, t.month, t.day) for t in day_obs_datetime]
    day_obs_iso8601 = tuple(str(d) for d in day_obs_date)
    visits.insert(1, "day_obs_mjd", day_obs_mjd)
    visits.insert(2, "day_obs_date", day_obs_date)
    visits.insert(3, "day_obs_iso8601", day_obs_iso8601)
    return visits


def add_coords_tuple(visits):
    """Add a coord tuple to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFrame with a 'coords' column that has an RA, dec tuple
    """
    coord_column = max(tuple(visits.columns).index("fieldRA"), tuple(visits.columns).index("fieldDec")) + 1
    visits.insert(coord_column, "coords", list(zip(visits["fieldRA"], visits["fieldDec"])))
    return visits


def add_maf_metric(visits, metric, column_name, constraint=None, nighbor_column=None):
    """Add a t_eff column to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns
    `metric` : `rubin_sim.maf.metrics.BaseMetric`
        The metric to compute.
    `column_name` : `str`
        The name for the column with the metric value.
    `constraint` : `str`
        The conditions used to load the visits.

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFrame with a t_eff column.
    """
    if nighbor_column is None:
        col_index = len(visits.columns)
    else:
        col_index = tuple(visits.columns).index(nighbor_column)

    value = schedview.compute.compute_metric_by_visit(visits, metric, constraint)
    visits.insert(col_index, column_name, value)
    return visits


def add_overhead(visits):
    """Add columns with overhead between exposures to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFrame with additonal columns: overhead (in seconds)
        and previous_filter.
    """
    overhead = (
        visits["observationStartMJD"].diff() * 24 * 60 * 60
        - visits["visitTime"].shift(1)
        + visits["visitTime"]
        - visits["visitExposureTime"]
    )
    slew_time_col_index = tuple(visits.columns).index("slewTime")
    visits.insert(slew_time_col_index + 1, "overhead", overhead)

    filter_col_index = tuple(visits.columns).index("filter")
    previous_filter = visits["filter"].shift(1)
    visits.insert(filter_col_index + 1, "previous_filter", previous_filter)
    return visits


def compute_overhead_summary(visits, sun_n12_setting, sun_n12_rising):
    """Create a dictionary of overhead summary stats.

    Parameters
    ----------
    `visits` : `pandas.DataFrame`
        The table of visits, with overhead data (see add_overhead)
    `sun_n12_setting`: `float`
        The MJD of evening twilight.
    `sun_n12_rising`: `float`
        The MJD of morning twilight.

    Returns
    -------
    `summary` : `dict`
        A dictionary of summary statistics
    """
    visit_start = visits["observationStartMJD"]
    visit_end = visit_start + visits["visitTime"] / (24 * 60 * 60)

    relative_start_time = (visit_start.min() - sun_n12_setting) * 60 * 24
    relative_end_time = (visit_end.max() - sun_n12_rising) * 60 * 24
    total_time = (visit_end.max() - visit_start.min()) * 24
    num_exposures = len(visits)
    total_exptime = visits.visitExposureTime.sum() / (60 * 60)
    mean_gap_time = 60 * 60 * (total_time - total_exptime) / (num_exposures - 1)
    median_gap_time = visits.overhead.median()

    summary = {
        "relative_start_time": relative_start_time,
        "relative_end_time": relative_end_time,
        "total_time": total_time,
        "num_exposures": num_exposures,
        "total_exptime": total_exptime,
        "mean_gap_time": mean_gap_time,
        "median_gap_time": median_gap_time,
    }

    return summary


def add_instrumental_fwhm(visits):
    """Add columns with overhead between exposures to a visits DataFrame.

    Parameter
    ---------
    `visits` : `pandas.DataFrame`
        The DataFrame of visits to which to add day_obs columns

    Returns
    -------
    `visits` : `pandas.DataFrame`
        The modified DataFRame with additonal columns: overhead (in seconds)
        and previous_filter.
    """
    # Get a seeing model that applies atmospheric and wavelength corrections,
    # but not instrumental contributions.
    seeing_model = SeeingModel(telescope_seeing=0.0, optical_design_seeing=0.0, camera_seeing=0.0)
    seeing_indx_dict = {b: i for i, b in enumerate(seeing_model.band_list)}

    noninst_seeing = np.array(
        tuple(
            seeing_model(v.seeingFwhm500, v.airmass)["fwhmEff"][seeing_indx_dict[v["filter"]]].item()
            for i, v in visits.iterrows()
        )
    )

    inst_fwhm = np.sqrt(visits["seeingFwhmEff"] ** 2 - noninst_seeing**2)
    seeing_col_index = tuple(visits.columns).index("seeingFwhmEff")
    visits.insert(seeing_col_index, "inst_fwhm", inst_fwhm)

    return visits


def accum_teff_by_night(visits):
    """Create a DataFrame of accumulated t_eff by target/band/night.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        A DataFrame of visits with (at least) the following columns:

        ``"day_obs_iso8601"``
            The day_obs (as defined in SITCOMTN-32) in YYYY-MM-DD format
            (`str`),
        ``"teff"``
            The effective exposure time (`float`).
        ``"filter"``
            The filter (`str`).
        ``"target_name"``
            The target name (`str`).

    Returns
    -------
    nightly_teff : `pandas.DataFrame`
        A `pandas.DataFrame` with the `target` as its index, `day_obs_iso8601`
        as its first column, and filter names for its remaining columns.
        Values for the columns with filter names are the total effective
        exposure times for all exposures with that target on that night.
    """
    day_obs_col = "day_obs_iso8601"
    teff_col = "t_eff"

    if day_obs_col not in visits:
        raise ValueError(
            f"{day_obs_col} column not found for visits; use the rubin_sim.maf.stackers.DayObsISOStacker."
        )

    if teff_col not in visits:
        raise ValueError(
            f"{teff_col} column not found for visits; use the rubin_sim.maf.stackers.TeffStacker."
        )

    nightly_teff = visits.groupby(["target_name", day_obs_col, "filter"])[teff_col].sum().reset_index()
    nightly_teff = (
        nightly_teff.pivot(index=["target_name", day_obs_col], columns="filter", values=teff_col)
        .fillna(0.0)
        .reset_index()
        .set_index(["target_name", day_obs_col])
    )
    return nightly_teff
