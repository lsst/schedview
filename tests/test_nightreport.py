import json
import unittest
import unittest.mock

import astropy.utils.iers
import requests.models

import schedview.compute.nightreport
import schedview.plot.nightreport
import schedview.plot.timeline
from schedview.collect import get_night_narrative, get_night_report

MOCK_NIGHTREPORT_RESPONSE = [
    {
        "id": "1",
        "date_added": "2024-12-05T02:00:00.1",
        "date_sent": "2024-12-05T03:00:00.1",
        "is_valid": False,
        "telescope": "Simonyi",
        "day_obs": 20241204,
        "summary": "First summary",
    },
    {
        "id": "2",
        "date_added": "2024-12-05T02:10:00.1",
        "date_sent": "2024-12-05T03:10:00.1",
        "is_valid": True,
        "telescope": "Simonyi",
        "day_obs": 20241204,
        "summary": "Second summary",
    },
    {
        "id": "3",
        "date_added": "2024-12-05T02:20:00.1",
        "date_sent": "2024-12-05T03:20:00.1",
        "is_valid": False,
        "telescope": "Simonyi",
        "day_obs": 20241204,
        "summary": "Third summary",
    },
]

# Only check for keys schedview actually requires (or is planned to require),
# not all that might be present.
REQUIRED_NARRATIVE_KEYS = set(
    [
        "message_text",
        "date_begin",
        "is_human",
        "is_valid",
        "date_added",
        "date_end",
        "components",
        "category",
        "time_lost_type",
    ]
)

MOCK_NARRATIVE_RESPONSE = [
    {
        "id": "1",
        "site_id": "summit",
        "message_text": "First narrative message",
        "time_lost": 0.0,
        "date_begin": "2024-12-05T02:00:22.3",
        "is_human": True,
        "is_valid": True,
        "date_added": "2024-12-05T03:00:05.01",
        "date_end": "2024-12-05T02:56:00.3",
        "components": ["MainTel"],
        "category": "None",
        "time_lost_type": "fault",
    },
    {
        "id": "2",
        "site_id": "summit",
        "message_text": "Second narrative message",
        "time_lost": 0.0,
        "date_begin": "2024-12-05T03:00:22.3",
        "is_human": True,
        "is_valid": True,
        "date_added": "2024-12-05T04:00:05.01",
        "date_end": "2024-12-05T03:56:00.3",
        "components": ["MainTel"],
        "category": "None",
        "time_lost_type": "fault",
    },
]

TEST_DAY_OBS = "2024-12-04"

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"


class TestNightReport(unittest.TestCase):

    @unittest.mock.patch("schedview.collect.logdb.requests.get")
    def test_get_night_report(self, mock_requests_get):
        response_to_get = requests.models.Response()
        response_to_get.status_code = 200
        response_to_get.json = unittest.mock.MagicMock(return_value=MOCK_NIGHTREPORT_RESPONSE)
        mock_requests_get.return_value = response_to_get

        night_report = get_night_report(TEST_DAY_OBS, "Simonyi")
        assert json.dumps(night_report) == json.dumps(MOCK_NIGHTREPORT_RESPONSE)

    @unittest.mock.patch("schedview.collect.logdb.requests.get")
    def test_get_night_narrative(self, mock_requests_get):
        response_to_get = requests.models.Response()
        response_to_get.status_code = 200
        response_to_get.json = unittest.mock.MagicMock(return_value=MOCK_NARRATIVE_RESPONSE)
        mock_requests_get.return_value = response_to_get

        night_narrative = get_night_narrative(TEST_DAY_OBS, "Simonyi")
        assert json.dumps(night_narrative) == json.dumps(MOCK_NARRATIVE_RESPONSE)

    def test_best_night_report(self):
        selected_report = schedview.compute.nightreport.best_night_report(MOCK_NIGHTREPORT_RESPONSE)
        assert selected_report["id"] == "2"

    def test_night_report_markdown(self):
        text = schedview.plot.nightreport.night_report_markdown(MOCK_NIGHTREPORT_RESPONSE[1])
        assert isinstance(text, str)

    def test_narrative_message_markdown(self):
        text = schedview.plot.nightreport.narrative_message_markdown(MOCK_NARRATIVE_RESPONSE[1])
        assert isinstance(text, str)

    def test_narrative_message_html(self):
        text = schedview.plot.nightreport.narrative_message_html(MOCK_NARRATIVE_RESPONSE[1])
        assert isinstance(text, str)

    def test_scrolling_narrative_messages_html(self):
        text = schedview.plot.nightreport.scrolling_narrative_messages_html(MOCK_NARRATIVE_RESPONSE)
        assert isinstance(text, str)
