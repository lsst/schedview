from tempfile import TemporaryDirectory

from astropy.time import Time
from matplotlib.figure import Figure

import rubin_sim
from rubin_sim import maf
from rubin_sim.scheduler.model_observatory import ModelObservatory
import schedview.compute.maf_metrics
from schedview.plot.maf import create_sample_maf_metric_plot

OPSIM_OUTPUT_FNAME = rubin_sim.data.get_baseline()
NIGHT = Time("2023-10-04", scale="utc")
OBSERVATORY = ModelObservatory()


def test_compute_sample_metric_bundle_group():
    with TemporaryDirectory() as data_dir:
        metric_bundle_group = (
            schedview.compute.maf_metrics.compute_sample_metric_bundle(
                OPSIM_OUTPUT_FNAME, data_dir, NIGHT, OBSERVATORY
            )
        )
        assert isinstance(metric_bundle_group, maf.MetricBundleGroup)


def test_create_sample_maf_metric_plot():
    with TemporaryDirectory() as data_dir:
        figure = create_sample_maf_metric_plot(OPSIM_OUTPUT_FNAME, data_dir, NIGHT)

    assert isinstance(figure, Figure)
