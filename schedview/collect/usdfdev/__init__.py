import schedview.clientsite

from ..efd import SAL_INDEX_GUESSES, query_efd_topic_for_night, sync_query_efd_topic_for_night
from ..logdb import get_from_logdb_with_retries

schedview.clientsite.DATASOURCE_BASE_URL = "https://usdf-rsp-dev.slac.stanford.edu/"
schedview.clientsite.EFD_NAME = "usdf_efd"
