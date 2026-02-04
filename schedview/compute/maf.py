import datetime
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from rubin_scheduler.scheduler.utils import SchemaConverter
from rubin_sim import maf

from schedview.util import band_column

__all__ = ["compute_metric_by_visit", "compute_scalar_metric_at_mjd", "compute_mixed_scalar_metric_at_mjd"]


def _visits_to_opsim(visits, opsim):
    # Take advantage of the schema migration code in SchemaConverter to make
    # sure we have up to date column names.
    schema_converter = SchemaConverter()
    obs = schema_converter.opsimdf2obs(visits)
    updated_opsim = schema_converter.obs2opsim(obs)

    # We can't just use the update opsim as is, because it might drop columns
    # we want. Instead, merge the results back into the visits passed to us.
    restored_columns = set(visits.columns) - set(updated_opsim.columns)
    restored_columns.add("observationId")
    norm_visits = (
        visits.reset_index()
        if "observationId" not in visits.columns and visits.index.name == "observationId"
        else visits
    )

    merged_opsim = updated_opsim.merge(
        norm_visits.loc[:, list(restored_columns)], on="observationId", suffixes=("", "_orig")
    )

    # If the round trip change actually changes values in an existing column
    # without changing the names, the merge might not work correctly. If
    # this happens, the default "inner join" performed by DataFrame.merge
    # will drop visits. Double check that this hasn't happened.
    assert len(merged_opsim) == len(visits)

    with sqlite3.connect(opsim) as con:
        merged_opsim.to_sql("observations", con)


def compute_metric(visits, metric_bundle, sqlite=True):
    """Compute metrics with MAF.

    Parameters
    ----------
    visits : `pandas.DataFrame`
        The DataFrame of visits (with column names matching those of opsim
        database).
    metric_bundle : `maf.MetricBundle`, `dict`, or `list` of `maf.MetricBundle`
        The metric bundle(s) to run.
    sqlite : `bool`
        Write visits to an sqlite3 database and then read the visits back
        from it when computing the metrics. Needed when metric bundles have
        constraints.

    Returns
    -------
    bundle_group : `maf.MetricBundleGroup`
        The metric bundle group with the results.
    """
    passed_one_bundle = isinstance(metric_bundle, maf.MetricBundle)
    metric_bundles = [metric_bundle] if passed_one_bundle else metric_bundle

    with TemporaryDirectory() as working_dir:
        if sqlite:
            visits_db = Path(working_dir).joinpath("visits.db").as_posix()
            _visits_to_opsim(visits, visits_db)

            bundle_group = maf.MetricBundleGroup(metric_bundles, visits_db, out_dir=working_dir)
            bundle_group.run_all()
        else:
            bundle_group = maf.MetricBundleGroup(metric_bundles, None, out_dir=working_dir)
            bundle_group.run_current(None, visits.to_records(index=False))

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
    if "observationId" not in visits.columns and visits.index.name == "observationId":
        visits = visits.reset_index()

    slicer = maf.OneDSlicer("observationId", bin_size=1)
    metric_bundle = maf.MetricBundle(slicer=slicer, metric=metric, constraint=constraint)

    # If the constraint is set, we need to use sqlite
    use_sqlite = len(constraint) > 0

    compute_metric(visits, metric_bundle, sqlite=use_sqlite)
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
    used_bands = visits[band_column(visits)].unique()

    # If the constraint is set, we need to use sqlite
    use_sqlite = len(constraint) > 0

    bundles = {}
    for this_band in used_bands:
        band_visits = visits.query(f"{band_column(visits)} == '{this_band}'")
        slicer = maf.HealpixSlicer(nside=nside, verbose=False)
        bundles[this_band] = maf.MetricBundle(metric, slicer, constraint)
        compute_metric(band_visits, bundles[this_band], sqlite=use_sqlite)

    metric_values = {b: bundles[b].metric_values for b in bundles if bundles[b].metric_values is not None}

    return metric_values


def compute_scalar_metric_at_mjd(
    visits,
    slicer,
    metric,
    mjd,
    summary_metric=None,
    run_name=None,
    query="",
    mjd_column="observationStartMJD",
):
    visits = visits.loc[visits[mjd_column] < mjd, :]

    if len(query) > 0:
        visits = visits.query(query)

    if len(visits) == 0:
        return np.nan

    if run_name is None:
        run_name = "Run" + datetime.datetime.now().isoformat()

    if summary_metric is not None:
        bundle = maf.MetricBundle(
            metric,
            slicer,
            summary_metrics=[summary_metric],
            run_name=run_name,
        )
    else:
        bundle = maf.MetricBundle(
            metric,
            slicer,
            run_name=run_name,
        )

    compute_metric(visits, bundle, sqlite=False)

    if summary_metric is None:
        metric_name = metric.name
        metric_values = bundle.metric_values
    else:
        bundle.compute_summary_stats()
        metric_name = summary_metric.name
        metric_values = (
            tuple(bundle.summary_values.values())
            if isinstance(bundle.summary_values, Mapping)
            else bundle.summary_values
        )

    assert len(metric_values) == 1
    return {metric_name: metric_values[0]}


def compute_mixed_scalar_metric_at_mjd(
    start_visits, end_visits, transition_mjd, *args, mjd_column="observationStartMJD", **kwargs
):
    visits = pd.concat(
        (
            start_visits.loc[start_visits[mjd_column] <= transition_mjd, :].dropna(axis="columns", how="all"),
            end_visits.loc[transition_mjd < end_visits[mjd_column], :].dropna(axis="columns", how="all"),
        )
    )
    result = compute_scalar_metric_at_mjd(visits, *args, **kwargs)
    return result
