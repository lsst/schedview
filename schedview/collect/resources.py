from lsst.resources import ResourcePath
from rubin_scheduler.sim_archive import read_archived_sim_metadata


def find_file_resources(base_resource_uri, file_filter=None):
    """Find matching files in a resource.

    Parameters
    ----------
    base_resource_uri : `str`
        The uri of the resource to search
    file_filter : `str` or `re.Pattern`, optional
        Regex to filter out files from the list before it is returned.

    Returns
    -------
    files : `list` of `str`
        The list of matching files available at the resource.
    """
    base_resource = ResourcePath(base_resource_uri)
    accumulated_files = []
    for dir_path, dir_names, file_names in base_resource.walk(file_filter=file_filter):
        for file_name in file_names:
            qualified_file_name = dir_path.join(file_name).geturl()
            if qualified_file_name not in accumulated_files:
                accumulated_files.append(qualified_file_name)

    return accumulated_files


def find_archive_resources(base_resource_uri, file_key=None, latest_date=None, num_nights=5):
    """Find matching files in a resource.

    Parameters
    ----------
    base_resource_uri : `str`
        The uri of the resource to search
    file_key : `str`
        The file time as keyed in the archive metadata files.
    latest_date : `str`, optional
        The date of the latest simulation to return.
    num_nights : `int`, optional
        The with of the date window to search for simulations.

    Returns
    -------
    files : `dict`
        The dictionary of matching resources.
    """
    accumulated_files = {}
    sim_metadata = read_archived_sim_metadata(base_resource_uri, latest=latest_date, num_nights=num_nights)

    for sim_uri, sim_metadata in sim_metadata.items():
        try:
            label = sim_metadata["label"]
            accumulated_files[label] = sim_uri
        except KeyError:
            pass

    return accumulated_files
