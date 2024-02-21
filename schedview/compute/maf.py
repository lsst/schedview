from tempfile import TemporaryDirectory

import pandas as pd
from lsst.resources import ResourcePath
from rubin_sim import maf

__all__ = ["compute_metric_by_visit"]


def compute_metric_by_visit(visits_rp, metric, constraint=""):
    """Compute a MAF metric by visit.

    Parameters
    ----------
    visits_rp : `lsst.resources.ResourcePath` or `str`
        The resource path for the visit database.
    metric : `rubin_sim.maf.metrics.BaseMetric`
        The metric to compute.
    constraint : `str`
        The SQL query to filter visits to be used.

    Returns
    -------
    values : `pandas.Series`
        The metric values.
    """
    if not isinstance(visits_rp, ResourcePath):
        visits_rp = ResourcePath(visits_rp)

    slicer = maf.OneDSlicer("observationId", bin_size=1)
    bundle = maf.MetricBundle(metric, slicer, constraint, run_name="anonymous")
    with TemporaryDirectory() as out_dir:
        with visits_rp.as_local() as visits_local_rp:
            bundle_group = maf.MetricBundleGroup([bundle], visits_local_rp.ospath, out_dir=out_dir)
            bundle_group.run_all()
            result = pd.Series(
                bundle.metric_values, index=bundle.slicer.slice_points["bins"][:-1].astype(int)
            )
            result.index.name = "observationId"
    return result
