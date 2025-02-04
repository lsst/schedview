import asyncio
import unittest

import pandas as pd

from schedview.collect import query_efd_topic_for_night, sync_query_efd_topic_for_night


class TestEfdAccess(unittest.TestCase):
    test_topic = "lsst.sal.Scheduler.logevent_largeFileObjectAvailable"
    test_date = "2024-12-10"
    test_sal_indexes = (1, 2, 3)

    @unittest.skip("Skipping test that requires EFD access")
    def test_query_efd_topic_for_night(self):
        async def waited_query_efd_topic_for_night(topic, date, sal_indexes):
            return await query_efd_topic_for_night(topic, date, sal_indexes)

        data = asyncio.run(
            waited_query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes)
        )
        assert isinstance(data, pd.DataFrame)

    @unittest.skip("Skipping test that requires EFD access")
    def test_sync_query_efd_topic_for_night(self):
        data = sync_query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes)
        assert len(data) > 0
        assert isinstance(data, pd.DataFrame)

        all_indexes_data = sync_query_efd_topic_for_night(self.test_topic, self.test_date)
        assert len(all_indexes_data) >= len(data)
        assert isinstance(all_indexes_data, pd.DataFrame)
