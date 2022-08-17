import importlib.resources
from os import environ

__all__ = ["get_metric_path"]


def get_metric_path():
    """Get the path to a file with numpy metrics

    Returns
    -------
    metric_path : `str`
        The path to the file containing the MAF metric
    """
    if "PICKLE_FNAME" in environ:
        return environ["PICKLE_FNAME"]

    root_package = __package__.split(".")[0]
    base_fname = "baseline_v2_0_10yrs_CoaddM5_r_HEAL.npz"

    try:
        fname = str(
            importlib.resources.files(root_package).joinpath("data", base_fname)
        )
    except AttributeError as e:
        # If we are using an older version of importlib, we need to do
        # this instead:
        if e.args[0] != "module 'importlib.resources' has no attribute 'files'":
            raise e

        with importlib.resources.path(root_package, ".") as root_path:
            fname = str(root_path.joinpath("data", base_fname))

    return fname

    return fname
