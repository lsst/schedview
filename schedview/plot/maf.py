import matplotlib.pyplot as plt

from rubin_sim import maf
import schedview.compute.maf_metrics


def plot_maf_metric_bundle(bundle_group):
    """Plot a MAF metric bundle

    Parameters
    ----------
    bundle_group : `rubin_sim.maf.metric_bundles.metric_bundle_group.MetricBundleGroup`
        The MAF bundle group from which to make the plot.

    Returns
    -------
    figure : `matplotlib.figure.Figure`
        The figure with the plot.
    """
    plot_handler = maf.PlotHandler()
    plot_handler.set_metric_bundles(bundle_group.bundle_dict)
    fig_num = plot_handler.plot(plot_func=maf.OneDBinnedData())
    figure = plt.figure(fig_num)
    return figure


def create_sample_maf_metric_plot(opsim_fname, data_dir, night, observatory=None):
    """Create a sample plot made from a MAF metric.

    Parameters
    ----------
    opsim_fname : `str`
        Name of file with opsim output.
    data_dir : `str`
        The MAF output directory
    night : `astropy.time.Time`
        The night for which to make the plot.
    observatory : , optional
        _description_, by default None

    Returns
    -------
    observatory : `rubin_sim.scheduler.model_observatory.model_observatory.ModelObservatory`, optional
        The observatory to use, by default None
    """
    bundle_group = schedview.compute.maf_metrics.compute_sample_metric_bundle(
        opsim_fname, data_dir, night, observatory
    )
    figure = plot_maf_metric_bundle(bundle_group)
    return figure
