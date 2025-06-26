import io
import os
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import schedview.app.prenight_inventory
from schedview import DayObs

TEST_ARCHIVE_SIM_METADATA = {
    "s3://rubin:rubin-scheduler-prenight/opsim/2025-06-30/1/": {
        "scheduler_version": "3.10.0",
        "opsim_config_repository": "https://github.com/lsst-ts/ts_config_ocs",
        "opsim_config_script": "ts_config_ocs/Scheduler/feature_scheduler/auxtel/fbs_spec_flex_survey.py",
        "opsim_config_version": "v0.28.12-68-g4bf56c5",
        "telescope": "auxtel",
        "label": "Test auxtel entry",
        "files": {
            "environment": {"md5": "e8eb7cd0f1ec0278d4678421501c18c8", "name": "environment.txt"},
            "observations": {"md5": "2f3be1c3ecdb7681e8372aa6c91f7344", "name": "opsim.db"},
        },
        "tags": ["ideal", "nominal"],
        "simulated_dates": {"first": "2025-06-30", "last": "2025-07-02"},
    },
    "s3://rubin:rubin-scheduler-prenight/opsim/2025-06-30/10/": {
        "scheduler_version": "3.10.0",
        "opsim_config_repository": "https://github.com/lsst-ts/ts_config_ocs",
        "opsim_config_script": "ts_config_ocs/Scheduler/feature_scheduler/maintel/fbs_config_sv_survey.py",
        "opsim_config_version": "v0.28.12-68-g4bf56c5",
        "telescope": "simonyi",
        "label": "test simonyi entry",
        "files": {
            "environment": {"md5": "e8eb7cd0f1ec0278d4678421501c18c8", "name": "environment.txt"},
            "observations": {"md5": "2f3be1c3ecdb7681e8372aa6c91f7344", "name": "opsim.db"},
        },
        "tags": ["ideal", "nominal"],
        "simulated_dates": {"first": "2025-06-30", "last": "2025-07-02"},
    },
}


class TestPrenightInventory(unittest.TestCase):

    @patch(
        "schedview.app.prenight_inventory.read_archived_sim_metadata",
        autospec=True,
    )
    def test_prenight_inventory(self, mock_read_archived_sim_metadata):
        mock_read_archived_sim_metadata.return_value = TEST_ARCHIVE_SIM_METADATA

        # get_prneight_table complains if these are not set.
        os.environ["LSST_DISABLE_BUCKET_VALIDATION"] = "1"
        if "S3_ENDPOINT_URL" not in os.environ:
            os.environ["S3_ENDPOINT_URL"] = "dummy"
        prenight_table = schedview.app.prenight_inventory.get_prenight_table(
            DayObs.from_date("2025-06-30"), "s3://rubin:rubin-scheduler-prenight/opsim/", num_nights=1
        )

        # make sure we can parse the output as a tab separated value string
        prenight_df = pd.read_csv(io.StringIO(prenight_table), sep="\t")

        # Is the data what we expect, given the fake data we fed it?
        assert len(prenight_df) == 2
        assert np.all(prenight_df.sim_execution_date == "2025-06-30")
        assert len(prenight_df.query('telescope=="simonyi"')) == 1
        assert len(prenight_df.query('telescope=="auxtel"')) == 1
        pass
