from urllib.parse import urlparse

from schedview.clientsite import LFA_SCHEME_NETLOC


def localize_lfa_url(url):
    """Localizes an LFA URL for a given site.

    Parameters
    ----------
    scheduler_url : `str`
        The LFA URL to be localized.

    Returns
    -------
    localized_url : `str`
        The localized UR.
    """
    path = urlparse(url).path
    localized_url = LFA_SCHEME_NETLOC + path
    return localized_url
