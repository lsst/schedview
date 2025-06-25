import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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

    @unittest.skipUnless(USE_CONSDB, "avoid requiring access to consdb for tests.")
    def test_consdb_read_consdb_with_token_file(self):
        if "ACCESS_TOKEN" in os.environ:
            token = os.environ["ACCESS_TOKEN"]
        else:
            try:
                import lsst.rsp

                token = lsst.rsp.get_access_token()
            except ImportError:
                return

        with TemporaryDirectory() as temp_dir:
            token_file = Path(temp_dir).joinpath("test_file")
            with open(token_file, "w") as token_io:
                token_io.write(token)

            day_obs: str = "2025-06-20"
            visits: pd.DataFrame = read_consdb("lsstcam", day_obs, token_file=token_file)
            assert len(visits) > 1
