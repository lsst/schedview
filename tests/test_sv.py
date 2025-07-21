import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rubin_scheduler.scheduler.utils import SchemaConverter

import schedview.collect.sv

USE_CONSDB = os.environ.get("TEST_WITH_CONSDB", "F").upper() in ("T", "TRUE", "1")


class TestReadSV(unittest.TestCase):

    @unittest.skipUnless(USE_CONSDB, "Skipping test requiring consdb access.")
    def test_get_sv_visits_cli(self):
        with TemporaryDirectory() as temp_dir:
            opsim_fname = str(Path(temp_dir).joinpath("read_sv_test_opsim.db"))
            cli_args = [opsim_fname, "--dayobs", "2025-07-20"]
            schedview.collect.sv.get_sv_visits_cli(cli_args)

            # send it round trip through the schema converter to make
            # sure the format is as expected.
            schema_converter = SchemaConverter()
            obs = schema_converter.opsim2obs(opsim_fname)
            visits = schema_converter.obs2opsim(obs)

            assert len(visits) > 100
