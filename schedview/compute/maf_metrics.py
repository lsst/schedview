from copy import deepcopy

from rubin_sim import maf
import schedview
import schedview.compute.astro

# Imported to help sphinx make the link
from rubin_sim.scheduler.model_observatory import ModelObservatory  # noqa F401
from rubin_sim.maf import MetricBundleGroup  # noqa F401


def compute_night_metric_bundle(
    opsim_fname, data_dir, night_date, metric, slicer, constraint, observatory=None
):
    """Create and run a MAF metric bundle before and after a night.

    Parameters
    ----------
    opsim_fname : `str`
        Name of file with opsim output.
    data_dir : `str`
        MAF output directory.
    night_date : `astropy.time.Time`
        The night to examine.
    metric : `rubin_sim.maf.metrics.base_metric.BaseMetric`
        The MAF metric to compute.
    slicer : `rubin_sim.maf.slicers.base_slicer.BaseSlicer`
        The MAF slicer to apply.
    constraint : `str`
        The SQL constraint on visits to include.
    observatory : `ModelObservatory`, optional
        The observatory to use, by default None

    Returns
    -------
    bundle_group: `MetricBundleGroup`
        The executed MAF metric bundle group.
    """
    site = None if observatory is None else observatory.location
    night_events = schedview.compute.astro.night_events(
        night_date=night_date, site=site
    )
    start_mjd = night_events.loc["sunset", "MJD"]
    end_mjd = night_events.loc["sunrise", "MJD"]

    bundles = {
        "before": maf.MetricBundle(
            metric=deepcopy(metric),
            slicer=deepcopy(slicer),
            constraint=f"{constraint} AND observationStartMJD < {start_mjd}",
            plot_dict={"color": "b"},
        ),
        "after": maf.MetricBundle(
            metric=deepcopy(metric),
            slicer=deepcopy(slicer),
            constraint=f"{constraint} AND observationStartMJD < {end_mjd}",
            plot_dict={"color": "r"},
        ),
    }

    bundle_group = maf.MetricBundleGroup(bundles, opsim_fname, out_dir=data_dir)
    bundle_group.run_all()

    return bundle_group


def compute_sample_metric_bundle(opsim_fname, data_dir, night_date, observatory=None):
    """Compute a sample MAF metric bundle before and after a night.

    Parameters
    ----------
    opsim_fname : `str`
        Name of file with opsim output
    data_dir : `str`
        MAF output directory
    night_date : `astropy.time.Time`
        Night to make the metric bundle for.
    observatory : `ModelObservatory`, optional
        The observatory to use, by default None

    Returns
    -------
    bundle_group: `rubin_sim.maf.MetricBundleGroup`
        The executed MAF metric bundle group.
    """
    metric = maf.CountMetric(col="observationId")
    slicer = maf.OneDSlicer(
        slice_col_name="fieldRA", bin_min=0, bin_max=360, bin_size=360 / 24
    )
    constraint = "filter = 'g'"
    bundle_group = compute_night_metric_bundle(
        opsim_fname, data_dir, night_date, metric, slicer, constraint, observatory
    )
    return bundle_group
