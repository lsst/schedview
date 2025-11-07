__all__ = ["read_scheduler", "sample_pickle"]

import bz2
import gzip
import importlib.resources
import lzma
import os
import pickle
from collections.abc import Sequence

from lsst.resources import ResourcePath
from rubin_scheduler.scheduler.model_observatory import ModelObservatory
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler

try:
    PICKLE_FNAME = os.environ["SCHED_PICKLE"]
except KeyError:
    PICKLE_FNAME = None


def read_local_scheduler_pickle(file_name, everything=False):
    """Read an instance of a scheduler object from a pickle.

    Parameters
    ----------
    file_name : `str`
        The name of the pickle file from which to load the scheduler.
    everything : `bool`
        Return everything in the pickle as it is stored instead of following
        the standard return.

    Returns
    -------
    scheduler : `rubin_scheduler.scheduler.schedulers.CoreScheduler`
        An instance of a rubin_scheduler scheduler object.
    conditions : `rubin_scheduler.scheduler.features.Conditions`
        An instance of a rubin_scheduler conditions object.
    """
    if file_name is None:
        file_name = PICKLE_FNAME

    if file_name is None:
        file_name = sample_pickle()

    if file_name.endswith(".bz2"):
        opener = bz2.open
    elif file_name.endswith(".xz"):
        opener = lzma.open
    elif file_name.endswith(".gz"):
        opener = gzip.open
    else:
        opener = open

    with opener(file_name, "rb") as pio:
        pickle_content = pickle.load(pio)

    if everything:
        return pickle_content

    match pickle_content:
        case CoreScheduler():
            scheduler = pickle_content
            conditions = None
        case Sequence():
            scheduler = pickle_content[0]
            conditions = pickle_content[1] if len(pickle_content) >= 2 else None
        case _:
            raise ValueError(f"Unrecognized content in pickle {file_name}")

    if conditions is None:
        try:
            conditions = scheduler.conditions
        except AttributeError:
            conditions = ModelObservatory(no_sky=True).return_conditions()

    return [scheduler, conditions]


def read_scheduler(file_name_or_url=None, everything=False):
    """Read an instance of a scheduler object from a pickle.

    Parameters
    ----------
    file_name : `str`
        The name or URL of the pickle file from which to load the scheduler.
    everything : `bool`
        Return everything in the pickle as it is stored instead of following
        the standard return.

    Returns
    -------
    scheduler : `rubin_scheduler.scheduler.schedulers.CoreScheduler`
        An instance of a rubin_scheduler scheduler object.
    conditions : `rubin_scheduler.scheduler.features.Conditions`
        An instance of a rubin_scheduler conditions object.
    """
    if file_name_or_url is None:
        file_name_or_url = PICKLE_FNAME

    if file_name_or_url is None:
        file_name_or_url = sample_pickle()

    scheduler_resource_path = ResourcePath(file_name_or_url)
    with scheduler_resource_path.as_local() as local_scheduler_resource:
        if everything:
            contents = read_local_scheduler_pickle(local_scheduler_resource.ospath, everything=True)
            return contents
        else:
            (scheduler, conditions) = read_local_scheduler_pickle(local_scheduler_resource.ospath)

    return scheduler, conditions


def sample_pickle(base_fname="sample_scheduler.pickle.xz"):
    """Return the path of the sample pickle

    Parameters
    ----------
    base_fname : `str`
        The base file name.

    Returns
    -------
    fname : `str`
        File name of the sample pickle.
    """
    root_package = __package__.split(".")[0]

    try:
        fname = str(importlib.resources.files(root_package).joinpath("data", base_fname))
    except AttributeError as e:
        # If we are using an older version of importlib, we need to do
        # this instead:
        if e.args[0] != "module 'importlib.resources' has no attribute 'files'":
            raise e

        with importlib.resources.path(root_package, ".") as root_path:
            fname = str(root_path.joinpath("data", base_fname))

    return fname
