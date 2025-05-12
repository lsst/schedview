from xml.etree import ElementTree

from schedview.compute.sim_archive import munge_sim_archive_metadata
from schedview.plot.sim_archive import make_html_table_of_sim_archive_metadata

TEST_SIM_ARCHIVE_RAW_METADATA = {
    "s3://rubin:rubin-scheduler-prenight/opsim/2025-01-04/1/": {
        "host": "sdfmilan108.sdf.slac.stanford.edu",
        "scheduler_version": "1.2.2.dev7+g6f1bd8b",
        "username": "neilsen",
        "label": "2025-01-04/1 Nominal start and overhead, ideal conditions, run at 2025-01-04 16:19:15.965",
        "opsim_config_branch": "main",
        "opsim_config_repository": "https://github.com/lsst-ts/ts_config_ocs.git",
        "opsim_config_script": "Scheduler/feature_scheduler/auxtel/fbs_config_image_photocal_survey.py",
        "files": {
            "environment": {"md5": "610e71ca3489dbe72880c1504d9fd161", "name": "environment.txt"},
            "observations": {"md5": "3cb12a748485301752fd4dac46af2618", "name": "opsim.db"},
            "pypi": {"md5": "b37b047f3b830bedbe775860de04ba93", "name": "pypi.json"},
            "rewards": {"md5": "366fb3e30030e4b07bfa0978a656c6e5", "name": "rewards.h5"},
            "scheduler": {"md5": "bde5c8206f4bf32c2f6b69d0f52b20a2", "name": "scheduler.pickle.xz"},
            "script": {"md5": "d58ce99de7446e7be4f59ed1df06b6ce", "name": "prenight.py"},
            "statistics": {"md5": "b49b72b21752fa28d423ec923d56510e", "name": "obs_stats.txt"},
        },
        "sim_runner_kwargs": {
            "mjd_start": 60680.034174948,
            "record_rewards": True,
            "survey_length": 2.0,
            "anomalous_overhead_func": "None",
        },
        "tags": ["ideal", "nominal"],
        "simulated_dates": {"first": "2025-01-04", "last": "2025-01-05"},
    },
    "s3://rubin:rubin-scheduler-prenight/opsim/2025-01-04/2/": {
        "host": "sdfmilan108.sdf.slac.stanford.edu",
        "scheduler_version": "1.2.2.dev7+g6f1bd8b",
        "username": "neilsen",
        "label": "2025-01-04/2 Start time delayed by 1 minutes, run at 2025-01-04 16:19:15.965",
        "opsim_config_branch": "main",
        "opsim_config_repository": "https://github.com/lsst-ts/ts_config_ocs.git",
        "opsim_config_script": "Scheduler/feature_scheduler/auxtel/fbs_config_image_photocal_survey.py",
        "files": {
            "environment": {"md5": "610e71ca3489dbe72880c1504d9fd161", "name": "environment.txt"},
            "observations": {"md5": "99ed4978b67a8dc48b88abb8a868320c", "name": "opsim.db"},
            "pypi": {"md5": "b37b047f3b830bedbe775860de04ba93", "name": "pypi.json"},
            "rewards": {"md5": "e0ca10adc9443e1dad8e52267161204e", "name": "rewards.h5"},
            "scheduler": {"md5": "85493412218a972ebe7eb290f3e9a1c3", "name": "scheduler.pickle.xz"},
            "script": {"md5": "d58ce99de7446e7be4f59ed1df06b6ce", "name": "prenight.py"},
            "statistics": {"md5": "5d525d009faa93c6814359659182bb8e", "name": "obs_stats.txt"},
        },
        "sim_runner_kwargs": {
            "mjd_start": 60680.034869392446,
            "record_rewards": True,
            "survey_length": 2.332810519685154,
            "anomalous_overhead_func": "None",
        },
        "tags": ["ideal", "delay_1"],
        "simulated_dates": {"first": "2025-01-04", "last": "2025-01-05"},
    },
}


def test_sim_archive_metadata():
    munged_sim_archive_metadata = munge_sim_archive_metadata(
        TEST_SIM_ARCHIVE_RAW_METADATA, "2025-01-04", "s3://rubin:rubin-scheduler-prenight/opsim/"
    )
    for sim_md in munged_sim_archive_metadata.values():
        assert "first_day_obs" in sim_md["simulated_dates"]

    sim_archive_table = make_html_table_of_sim_archive_metadata(munged_sim_archive_metadata)

    # Parse the html table, and make sure the outermost take is a table.
    # Because we are using the xml parser that comes with python intsead of a
    # real html parser, it fails with the ampersands in the URLs, so escape
    # them.
    parsed_table = ElementTree.fromstring(sim_archive_table.replace("&", "&amp;"))
    assert parsed_table.tag == "table"
