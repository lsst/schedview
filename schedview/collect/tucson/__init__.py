import schedview.clientsite

from ..efd import (
    SAL_INDEX_GUESSES,
    get_scheduler_config,
    get_version_at_time,
    make_efd_client,
    make_version_table_for_time,
    query_efd_topic_for_night,
    sync_query_efd_topic_for_night,
)
from ..logdb import get_from_logdb_with_retries

schedview.clientsite.DATASOURCE_BASE_URL = None
schedview.clientsite.EFD_NAME = "tucson_efd"
