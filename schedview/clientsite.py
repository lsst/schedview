# Conceptually, this file makes more sense to have in the "collect" submodule,
# but keeping this module at the "top" level of schedview rather than in the
# collect submodule avoids issues with circular imports.

import os
from warnings import warn

DATASOURCE_BASE_URL = None
EFD_NAME = None


def guess_site() -> str:
    """Try to guess the site from the environment.

    Returns
    -------
    site: `str`
        A key designating the client site.
    """
    site: str | None = None

    if site is None:
        # Try figuring out the site from EXTERNAL_INSTANCE_URL
        location = os.getenv("EXTERNAL_INSTANCE_URL", "")
        if "tucson-teststand" in location:
            site = "tucson"
        elif "summit-lsp" in location:
            site = "summit"
        elif "base-lsp" in location:
            site = "base"
        elif "usdf-rsp" in location:
            if "dev" in location:
                site = "usdf-dev"
            else:
                site = "usdf"
        else:
            warn(f"Could not determine site from EXTERNAL_INSTANCE_URL {location}.")

    if site is None:
        # Try figuring out the site from the hostname
        hostname = os.getenv("HOSTNAME", "")
        interactiveNodes = ("sdfrome", "sdfiana")
        if hostname.startswith(interactiveNodes):
            site = "usdf"
        elif hostname == "htcondor.ls.lsst.org":
            site = "base"
        elif hostname == "htcondor.cp.lsst.org":
            site = "summit"
        else:
            warn(f"Could not deterime site from HOSTNAME {hostname}.")

    if site is None:
        site = "local"

    return site
