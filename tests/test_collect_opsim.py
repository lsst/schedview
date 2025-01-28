import unittest

from schedview.collect import read_opsim


class TestCollectOpsim(unittest.TestCase):
    def test_read_opsim(self):
        test_rp = "resource://schedview/data/opsim_prenight_2024-08-13_1.db"
        visits = read_opsim(test_rp)
        assert "target_name" in visits.columns

        # 'target_name' used to be called 'target'.
        # Verify that read_opsim finds and renames it correctly
        old_test_rp = "resource://schedview/data/opsim_prenight_2024-07-30_1.db"
        old_visits = read_opsim(old_test_rp)
        assert "target_name" in old_visits.columns
