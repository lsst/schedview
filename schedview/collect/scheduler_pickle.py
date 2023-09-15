__all__ = ["read_scheduler", "sample_pickle"]

import bz2
import gzip
import importlib.resources
import lzma
import os
import pickle
import urllib
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from rubin_sim.scheduler.model_observatory import ModelObservatory

try:
    PICKLE_FNAME = os.environ["SCHED_PICKLE"]
except KeyError:
    PICKLE_FNAME = None


def read_local_scheduler_pickle(file_name):
    """Read an instance of a scheduler object from a pickle.

    Parameters
    ----------
    file_name : `str`
        The name of the pickle file from which to load the scheduler.

    Returns
    -------
    scheduler : `rubin_sim.scheduler.schedulers.core_scheduler.CoreScheduler`
        An instance of a rubin_sim scheduler object.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`
        An instance of a rubin_sim conditions object.
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

    try:
        with opener(file_name, "rb") as pio:
            scheduler, conditions = pickle.load(pio)

    except TypeError:
        with opener(file_name, "rb") as pio:
            scheduler = pickle.load(pio)

        try:
            conditions = scheduler.conditions
        except AttributeError:
            conditions = ModelObservatory().return_conditions()

    return [scheduler, conditions]


def read_scheduler(file_name_or_url=None):
    """Read an instance of a scheduler object from a pickle.

    Parameters
    ----------
    file_name : `str`
        The name or URL of the pickle file from which to load the scheduler.

    Returns
    -------
    scheduler : `rubin_sim.scheduler.schedulers.core_scheduler.CoreScheduler`
        An instance of a rubin_sim scheduler object.
    conditions : `rubin_sim.scheduler.features.conditions.Conditions`
        An instance of a rubin_sim conditions object.
    """
    if file_name_or_url is None:
        file_name_or_url = PICKLE_FNAME

    if file_name_or_url is None:
        file_name_or_url = sample_pickle()

    if Path(file_name_or_url).is_file():
        scheduler, conditions = read_local_scheduler_pickle(file_name_or_url)
    else:
        # If we didn't have do decompress it, we could use urlopen instead
        # of downloading a local copy. But, it can be compressed, so we need
        # to use gzip.open to open it.
        with TemporaryDirectory() as directory:
            with urllib.request.urlopen(file_name_or_url) as url_io:
                content = url_io.read()

            # Infer a file name
            parsed_url = urllib.parse.urlparse(file_name_or_url)
            origin_path = Path(parsed_url.path)
            origin_name = origin_path.name
            name = origin_name if len(origin_name) > 0 else "scheduler.pickle"
            path = Path(directory).joinpath(name)

            with open(path, "wb") as file_io:
                file_io.write(content)

            scheduler, conditions = read_local_scheduler_pickle(str(path))

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
