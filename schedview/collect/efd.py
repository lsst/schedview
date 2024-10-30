import os
from collections.abc import Iterable

import pandas as pd
from lsst_efd_client import EfdClient

from schedview.dayobs import DayObs

DEFAULT_EFD = (
    "summit_efd" if os.getenv("EXTERNAL_INSTANCE_URL", "") == "https://summit-lsp.lsst.codes" else "usdf_efd"
)
SAL_INDEX_GUESSES = {"lsstcomcam": [1], "latiss": [2]}


def _get_efd_client(efd: EfdClient | str | None) -> EfdClient:
    match efd:
        case EfdClient():
            efd_client = efd
        case str():
            efd_client = EfdClient(efd)
        case None:
            efd_client = EfdClient(DEFAULT_EFD)
        case _:
            raise ValueError(f"Cannot translate a {type(efd)} to an EfdClient.")

    return efd_client


async def _get_efd_fields_for_topic(efd_client, topic, public_only=True):
    fields = await efd_client.get_fields(topic)
    if public_only:
        fields = [f for f in fields if "private" not in f]

    return fields


def _guess_sal_indexes(instrument):
    return SAL_INDEX_GUESSES[instrument]


async def query_efd_topic_for_night(topic, instrument, day_obs, efd=None, fields=None, sal_indexes=None):
    day_obs = day_obs if isinstance(day_obs, DayObs) else DayObs.from_date(day_obs)
    efd_client = _get_efd_client(efd)

    if fields is None:
        fields = await _get_efd_fields_for_topic(efd_client, topic)

    if sal_indexes is None:
        sal_indexes = _guess_sal_indexes(instrument)

    if not isinstance(sal_indexes, Iterable):
        sal_indexes = [sal_indexes]

    results = []
    for sal_index in sal_indexes:
        result = await efd_client.select_time_series(
            topic, fields, day_obs.start, day_obs.end, index=sal_index
        )
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            results.append(result)

    result = pd.concat(results) if len(results) > 0 else pd.DataFrame()

    return result


async def query_latest_in_efd_topic(
    topic, instrument, num_records=6, efd=None, fields=None, sal_indexes=None
):
    efd_client = _get_efd_client(efd)

    if fields is None:
        fields = await _get_efd_fields_for_topic(efd_client, topic)

    if sal_indexes is None:
        sal_indexes = _guess_sal_indexes(instrument)

    if not isinstance(sal_indexes, Iterable):
        sal_indexes = [sal_indexes]

    results = []
    for sal_index in sal_indexes:
        result = await efd_client.select_top_n(topic, fields, num_records, index=sal_index)
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            results.append(result)

    result = pd.concat(results) if len(results) > 0 else pd.DataFrame()

    return result
