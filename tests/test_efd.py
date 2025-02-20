import asyncio
import os
import unittest

import pandas as pd
import pytest
from astropy.time import Time, TimeDelta

from schedview.collect import (
    get_version_at_time,
    make_version_table_for_time,
    query_efd_topic_for_night,
    sync_query_efd_topic_for_night,
)

USE_EFD = os.environ.get("TEST_WITH_EFD", "F").upper() in ("T", "TRUE", "1")


class TestEfdAccess(unittest.TestCase):
    test_topic = "lsst.sal.Scheduler.logevent_largeFileObjectAvailable"
    test_date = "2024-12-10"
    test_sal_indexes = (1, 2, 3)

    @unittest.skipUnless(USE_EFD, "Skipping test that requires EFD access")
    def test_query_efd_topic_for_night(self):
        async def waited_query_efd_topic_for_night(topic, date, sal_indexes):
            return await query_efd_topic_for_night(topic, date, sal_indexes)

        data = asyncio.run(
            waited_query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes)
        )
        assert isinstance(data, pd.DataFrame)

    @unittest.skipUnless(USE_EFD, "Skipping test that requires EFD access")
    def test_sync_query_efd_topic_for_night(self):
        data = sync_query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes)
        assert len(data) > 0
        assert isinstance(data, pd.DataFrame)

        all_indexes_data = sync_query_efd_topic_for_night(self.test_topic, self.test_date)
        assert len(all_indexes_data) >= len(data)
        assert isinstance(all_indexes_data, pd.DataFrame)

    @unittest.skipUnless(USE_EFD, "Skipping test that requires EFD access")
    def test_make_version_table_for_time(self):
        time_cut = Time("2024-12-05T12:00:00Z")
        result = make_version_table_for_time(time_cut)
        for item in ("ts_config_ocs", "cloudModel", "rubin_scheduler"):
            assert isinstance(result.loc[item, "version"], str)
            assert isinstance(result.loc[item, "time"], pd.Timestamp)

    @unittest.skipUnless(USE_EFD, "Skipping test that requires EFD access")
    def test_get_version_at_time(self):
        time_cut = Time("2024-12-05T12:00:00Z")
        test_version = get_version_at_time("rubin_scheduler", time_cut)
        assert isinstance(test_version, str)

        test_version = get_version_at_time("rubin_scheduler", time_cut, TimeDelta(365, format="jd"))
        assert isinstance(test_version, str)

        with pytest.raises(ValueError):
            test_version = get_version_at_time("rubin_scheduler", time_cut, TimeDelta(0.001, format="jd"))
