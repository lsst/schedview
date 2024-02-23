import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from rubin_sim import maf
from rubin_sim.scheduler.utils import SchemaConverter

__all__ = ["compute_metric_by_visit"]


def _visits_to_opsim(visits, opsim):
    # Only write columns in visits that are in opsim databases,
    # thereby avoiding added columns that might not be types
    # that can be written to sqlite databases.
    opsim_columns = list(SchemaConverter().convert_dict.keys())
    with sqlite3.connect(opsim) as connection:
        visits.reset_index()[opsim_columns].to_sql("observations", connection, index=False)


def compute_metric(visits, metric_bundle):
    """Compute metrics with MAF.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The DataFrame of visits (with column names matching those of opsim
        database).
    metric_bundle : `maf.MetricBundle`, `dict`, or `list` of `maf.MetricBundle`
        The metric bundle(s) to run.

    Returns
    -------
    bundle_group : `maf.MetricBundleGroup`
        The metric bundle group with the results.
    """
    passed_one_bundle = isinstance(metric_bundle, maf.MetricBundle)
    metric_bundles = [metric_bundle] if passed_one_bundle else metric_bundle

    with TemporaryDirectory() as working_dir:
        visits_db = Path(working_dir).joinpath("visits.db").as_posix()
        _visits_to_opsim(visits, visits_db)

        bundle_group = maf.MetricBundleGroup(metric_bundles, visits_db, out_dir=working_dir)
        bundle_group.run_all()

    return metric_bundle


def compute_metric_by_visit(visits, metric, constraint=""):
    """Compute a MAF metric by visit.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The DataFrame of visits (with column names matching those of opsim
        database).
    metric : `rubin_sim.maf.metrics.BaseMetric`
        The metric to compute.
    constraint : `str`
        The SQL query to filter visits to be used.

    Returns
    -------
    values : `pandas.Series`
        The metric values.
    """
    slicer = maf.OneDSlicer("observationId", bin_size=1)
    metric_bundle = maf.MetricBundle(slicer=slicer, metric=metric, constraint=constraint)

    compute_metric(visits, metric_bundle)
    result = pd.Series(metric_bundle.metric_values, index=slicer.slice_points["bins"][:-1].astype(int))
    result.index.name = "observationId"
    return result


def compute_hpix_metric_in_bands(visits, metric, constraint="", nside=32):
    """Compute a MAF metric by visit.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The DataFrame of visits (with column names matching those of opsim
        database).
    metric : `rubin_sim.maf.metrics.BaseMetric`
        The metric to compute.
    constraint : `str`
        The SQL query to filter visits to be used.
    nside : `int`
        The healpix nside of the healpix arrays to return.

    Returns
    -------
    metric_values : `dict`
        A dictionary of healpix arrays, where the keys are the filters with
        visits in the input visit DataFrame.
    """
    # Do only the filters we actually used
    used_filters = visits["filter"].unique()

    bundles = {}
    for this_filter in used_filters:
        this_constraint = f"filter == '{this_filter}'"
        if len(constraint) > 0:
            this_constraint += f" AND {constraint}"
        slicer = maf.HealpixSlicer(nside=nside)
        bundles[this_filter] = maf.MetricBundle(metric, slicer, this_constraint)

    compute_metric(visits, bundles)
    metric_values = {b: bundles[b].metric_values for b in bundles if bundles[b].metric_values is not None}

    return metric_values
