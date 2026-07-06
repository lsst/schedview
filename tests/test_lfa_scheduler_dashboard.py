import os
import unittest
from datetime import datetime

import pandas as pd
import pytest

# Objects to test instances against.
from rubin_scheduler.scheduler.features.conditions import Conditions
from rubin_scheduler.scheduler.schedulers.core_scheduler import CoreScheduler

import schedview.collect.efd
from schedview.app.scheduler_dashboard.scheduler_dashboard_app import LFASchedulerSnapshotDashboard


class _StubEfdClient:
    """A minimal stand-in for ``lsst_efd_client.EfdClient``.

    It ducktypes the query methods used by the snapshot-list code path and
    returns empty DataFrames, so the test does not depend on a real EFD
    connection, network access, or the installed ``lsst-efd-client`` version.
    """

    async def select_top_n(self, *args, **kwargs):
        return pd.DataFrame()

    async def select_time_series(self, *args, **kwargs):
        return pd.DataFrame()


@pytest.mark.asyncio
async def test_get_scheduler_list(monkeypatch):
    # Avoid constructing a real EfdClient (which reaches out to segwarides for
    # credentials and to InfluxDB for a health check).
    monkeypatch.setattr(schedview.collect.efd, "make_efd_client", lambda *a, **k: _StubEfdClient())

    scheduler = LFASchedulerSnapshotDashboard()
    scheduler.telescope = None
    await scheduler._async_get_scheduler_list()
    # No snapshots are retrieved from the stub client, so the dropdown keeps
    # its single empty default option.
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
