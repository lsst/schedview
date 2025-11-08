from lsst.resources import ResourcePath


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
