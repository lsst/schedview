import os
import unittest
from datetime import datetime

import pytest

# Objects to test instances against.
from rubin_scheduler.scheduler.features.conditions import Conditions
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler

from schedview.app.scheduler_dashboard.scheduler_dashboard_app import LFASchedulerSnapshotDashboard


@pytest.mark.asyncio
async def test_get_scheduler_list():
    scheduler = LFASchedulerSnapshotDashboard()
    scheduler.telescope = None
    await scheduler._async_get_scheduler_list()
    # No snapshots should be retreived if it isn't an LFA environment
    # the dropdown has one empty option
    assert len(scheduler.param.scheduler_fname.objects) >= 1


@unittest.skip("Skip until there are compatible schedulers in the LFA.")
@pytest.mark.asyncio
async def test_get_scheduler_list_in_USDF():
    scheduler = LFASchedulerSnapshotDashboard()

    scheduler.telescope = None
    scheduler.datetime_cut = datetime(2024, 10, 1, 21, 26, 23)
    await scheduler._async_get_scheduler_list()
    # make sure it's a LFA environment by checking
    # the env variables needed for LFA mode are set
    if os.environ.get("AWS_SHARED_CREDENTIALS_FILE") and os.environ.get("S3_ENDPOINT_URL"):
        # at least one snapshot file should be retreived
        # the dropdown should have one empty option +
        # at least one snapshot
        assert len(scheduler.param.scheduler_fname.objects) >= 2
        scheduler.scheduler_fname = scheduler.param["scheduler_fname"].objects[1]
        scheduler.read_scheduler()
        assert isinstance(scheduler._scheduler, CoreScheduler)
        assert isinstance(scheduler._conditions, Conditions)
    else:
        # pass the test if it isn't an LFA environment
        pass
