import datetime
import io
import os
import unittest
from unittest.mock import patch
from uuid import UUID

import pandas as pd
from pandas import Timestamp

import schedview.app.prenight_inventory
from schedview import DayObs

TEST_PRENIGHT_INDEX = pd.DataFrame(
    [
        {
            "comments": {},
            "conda_env_sha256": "",
            "config_url": None,
            "creation_time": Timestamp("2025-10-29 14:06:08.276173+0000", tz="UTC"),
            "daily_id": 2,
            "files": {
                "rewards": "s3://rubin:rubin-scheduler-prenight/opsim/vseq/simonyi/2025-10-29/40b559a3-16a1-4004-9ed6-644cef98ea84/rewards.h5"
            },
            "first_day_obs": datetime.date(2025, 10, 29),
            "last_day_obs": datetime.date(2025, 10, 31),
            "parent_last_day_obs": datetime.date(2025, 10, 28),
            "parent_visitseq_uuid": UUID("60a4a166-3dbc-4de0-8d38-d9933e243b9a"),
            "scheduler_version": "v3.18.1",
            "sim_creation_day_obs": datetime.date(2025, 10, 29),
            "sim_runner_kwargs": None,
            "tags": ["ideal", "nominal", "prenight"],
            "telescope": "simonyi",
            "visitseq_label": "Nominal start and overhead, ideal conditions, run at "
            "2025-10-29T07:02:28-07:00",
            "visitseq_url": "s3://rubin:rubin-scheduler-prenight/opsim/vseq/simonyi/2025-10-29/40b559a3-16a1-4004-9ed6-644cef98ea84/visits.h5",
            "visitseq_uuid": UUID("60a4a166-3dbc-4de0-8d38-d9933e243b9b"),
        },
        {
            "comments": {},
            "conda_env_sha256": "",
            "config_url": None,
            "creation_time": Timestamp("2025-10-29 14:12:06.321309+0000", tz="UTC"),
            "daily_id": 3,
            "files": {
                "rewards": "s3://rubin:rubin-scheduler-prenight/opsim/vseq/simonyi/2025-10-29/d86a1d28-11df-47e1-9d4d-9268166563fa/rewards.h5"
            },
            "first_day_obs": datetime.date(2025, 10, 29),
            "last_day_obs": datetime.date(2025, 10, 31),
            "parent_last_day_obs": datetime.date(2025, 10, 28),
            "parent_visitseq_uuid": UUID("60a4a166-3dbc-4de0-8d38-d9933e243b9a"),
            "scheduler_version": "v3.18.1",
            "sim_creation_day_obs": datetime.date(2025, 10, 29),
            "sim_runner_kwargs": None,
            "tags": ["delay_60", "ideal", "prenight"],
            "telescope": "auxtel",
            "visitseq_label": "Start time delayed by 60 minutes, nominal slew and visit "
            "overhead, ideal conditions, run at "
            "2025-10-29T07:06:57-07:00",
            "visitseq_url": "s3://rubin:rubin-scheduler-prenight/opsim/vseq/simonyi/2025-10-29/d86a1d28-11df-47e1-9d4d-9268166563fa/visits.h5",
            "visitseq_uuid": UUID("60a4a166-3dbc-4de0-8d38-d9933e243b9c"),
        },
    ]
).set_index("visitseq_uuid")


class TestPrenightInventory(unittest.TestCase):

    @patch(
        "schedview.app.prenight_inventory.get_prenight_index",
        autospec=True,
    )
    def test_prenight_inventory(self, mock_read_archived_sim_metadata):
        mock_read_archived_sim_metadata.return_value = TEST_PRENIGHT_INDEX

        # get_prneight_table complains if these are not set.
        os.environ["LSST_DISABLE_BUCKET_VALIDATION"] = "1"
        if "S3_ENDPOINT_URL" not in os.environ:
            os.environ["S3_ENDPOINT_URL"] = "dummy"
        prenight_table = schedview.app.prenight_inventory.get_prenight_table(DayObs.from_date("2025-10-29"))

        # make sure we can parse the output as a tab separated value string
        prenight_df = pd.read_csv(io.StringIO(prenight_table), sep="\t")

        # Is the data what we expect, given the fake data we fed it?
        assert len(prenight_df.query('telescope=="simonyi"')) == 2
        assert len(prenight_df.query('telescope=="auxtel"')) == 2
        pass
