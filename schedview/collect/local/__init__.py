import os
import warnings

import schedview.clientsite

from ..efd import (
    SAL_INDEX_GUESSES,
    make_efd_client,
    query_efd_topic_for_night,
    sync_query_efd_topic_for_night,
)
from ..logdb import get_from_logdb_with_retries

schedview.clientsite.DATASOURCE_BASE_URL = "https://usdf-rsp.slac.stanford.edu/"
schedview.clientsite.EFD_NAME = "usdf_efd"

if "SCHEDVIEW_DATASOURCE_URL" in os.environ:
    schedview.clientsite.DATASOURCE_BASE_URL = os.environ["SCHEDVIEW_DATASOURCE_URL"]
else:
    warnings.warn(
        f"SCHEDVIEW_DATASOURCE_URL env variable not set, using {schedview.clientsite.DATASOURCE_BASE_URL}"
    )

if "SCHEDVIEW_EFD_NAME" in os.environ:
    schedview.clientsite.DATASOURCE_BASE_URL = os.environ["SCHEDVIEW_EFD_NAME"]
else:
    warnings.warn(f"SCHEDVIEW_EFD_NAME environment variable not set, using {schedview.clientsite.EFD_NAME}")
