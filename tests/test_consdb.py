import os
import unittest

import pandas as pd
from rubin_sim import maf

from schedview.collect import read_consdb

USE_CONSDB = os.environ.get("TEST_WITH_CONSDB", "F").upper() in ("T", "TRUE", "1")


class TestConsdb(unittest.TestCase):

    @unittest.skipUnless(USE_CONSDB, "avoid requiring access to consdb for tests.")
    def test_consdb_read_consdb(self):
        day_obs: str = "2024-06-26"
        stackers = [
            maf.stackers.OverheadStacker(),
            maf.HourAngleStacker(),
            maf.stackers.ObservationStartDatetime64Stacker(),
        ]
        visits: pd.DataFrame = read_consdb("lsstcomcamsim", day_obs, stackers=stackers)
        assert "HA" in visits.columns
        assert "overhead" in visits.columns
