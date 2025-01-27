from typing import Literal

from schedview.collect.efd import ClientConnections
from schedview.collect.nightreport import get_night_narrative
from schedview.collect.visits import NIGHT_STACKERS, read_visits
from schedview.dayobs import DayObs

EFD_TOPIC_FOR_KEY = {
    "scheduler_dependencies": "lsst.sal.Scheduler.logevent_dependenciesVersions",
    "scheduler_configuration": "lsst.sal.Scheduler.logevent_configurationApplied",
    "block_status": "lsst.sal.Scheduler.logevent_blockStatus",
    "scheduler_snapshots": "lsst.sal.Scheduler.logevent_largeFileObjectAvailable",
}


async def collect_timeline_data(
    day_obs: str | int | DayObs,
    sal_indexes: tuple[int, ...] = (1, 2, 3),
    telescope: Literal["AuxTel", "Simonyi"] = "Simonyi",
    visit_origin: str = "lsstcomcam",
    **kwargs,
) -> dict:
    """Create a dictionary with data to put on a timeline, compatible with
    `schedview.plot.timeline.make_multitimeline`.

    Parameters
    ----------
    day_obs : `str` or `int` or `DayObs`
        Night for which to retrieve data
    sal_indexes : `tuple[int, ...]`, optional
        sal indexes from which to query EFD data    , by default (1, 2, 3)
    telescope : `str`, optional
        "AuxTel" or "Simonyi", by default "Simonyi"
    visit_origin : `str`, optional
        Source of visit data, by default "lsstcomcam"

    Returns
    -------
    timeline_data: `dict`
        Data for a timeline plot.
    """

    day_obs = DayObs.from_date(day_obs)

    data = {}
    requested_keys = [k for k in kwargs if kwargs[k]]

    efd_client_connections = ClientConnections()

    for key in requested_keys:
        if key == "visits":
            if "visit_timeline" in data:
                data[key] = data["visit_timeline"]
            else:
                data[key] = read_visits(day_obs, visit_origin, stackers=NIGHT_STACKERS)
        elif key == "visit_timeline":
            if "visits" in data:
                data[key] = data["visits"]
            else:
                data[key] = read_visits(day_obs, visit_origin, stackers=NIGHT_STACKERS)
        elif key == "log_messages":
            data[key] = get_night_narrative(day_obs, telescope)
        elif key in EFD_TOPIC_FOR_KEY:
            data[key] = await efd_client_connections.query_efd_topic_for_night(
                EFD_TOPIC_FOR_KEY[key], day_obs, sal_indexes
            )
        else:
            ValueError("Unrecognized data key: {key}")

    return data
