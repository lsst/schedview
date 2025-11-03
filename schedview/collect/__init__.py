__all__ = [
    "NIGHT_STACKERS",
    "SAL_INDEX_GUESSES",
    "find_file_resources",
    "get_footprint",
    "get_from_logdb_with_retries",
    "get_metric_path",
    "get_night_narrative",
    "get_night_report",
    "load_bright_stars",
    "make_efd_client",
    "query_efd_topic_for_night",
    "read_consdb",
    "read_ddf_visits",
    "read_multiple_prenights",
    "read_opsim",
    "read_rewards",
    "read_scheduler",
    "read_visits",
    "sample_pickle",
    "sync_query_efd_topic_for_night",
]


from warnings import warn

import schedview.clientsite

CLIENT_SITE = schedview.clientsite.guess_site()

match CLIENT_SITE:
    case "local":
        from .local import *
    case "summit":
        from .summit import *
    case "tucson":
        from .tucson import *
    case "base":
        from .base import *
    case "usdf":
        from .usdf import *
    case "usdf-dev":
        from .usdfdev import *
    case _:
        from .local import *

        warn(f"Unknown client site {CLIENT_SITE}. Using local configuration.")

# Imports that themselves import code that varies by site must be imported
# after the "match CLIENT_SITE" structure above to avoid circular
# dependencies.

# Any imports that vary by the site the client is running on should
# have their respective implementations in the relevant schedview.collect
# submodule, and then the correct version imported for each site in the
# "match CLIENT_SITE" structure above.
from .consdb import read_consdb
from .footprint import get_footprint
from .metrics import get_metric_path
from .multisim import read_multiple_prenights
from .nightreport import get_night_narrative, get_night_report
from .opsim import read_ddf_visits, read_opsim
from .resources import find_file_resources
from .rewards import read_rewards
from .scheduler_pickle import read_scheduler, sample_pickle
from .stars import load_bright_stars
from .visits import NIGHT_STACKERS, read_visits
