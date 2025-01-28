import asyncio
import unittest

import pandas as pd

from schedview.collect.efd import ClientConnections


class TestTimelinePlotters(unittest.TestCase):
    test_topic = "lsst.sal.Scheduler.logevent_largeFileObjectAvailable"
    test_date = "2024-12-10"
    test_sal_indexes = (1, 2, 3)

    @unittest.skip("Skipping test that requires EFD access")
    def test_query_efd_topic_for_night(self):

        clients = ClientConnections()

        async def query_efd_topic_for_night(topic, date, sal_indexes):
            return await clients.query_efd_topic_for_night(topic, date, sal_indexes)

        data = asyncio.run(query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes))
        assert isinstance(data, pd.DataFrame)

    @unittest.skip("Skipping test that requires EFD access")
    def test_sync_query_efd_topic_for_night(self):
        clients = ClientConnections()
        data = clients.sync_query_efd_topic_for_night(self.test_topic, self.test_date, self.test_sal_indexes)
        assert isinstance(data, pd.DataFrame)
