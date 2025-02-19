import schedview.clientsite

from ..efd import (
    SAL_INDEX_GUESSES,
    make_efd_client,
    query_efd_topic_for_night,
    sync_query_efd_topic_for_night,
)
from ..logdb import get_from_logdb_with_retries

schedview.clientsite.DATASOURCE_BASE_URL = "https://base-lsp.slac.lsst.codes/"
schedview.clientsite.EFD_NAME = "base_efd"
