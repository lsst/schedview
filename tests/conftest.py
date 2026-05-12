from __future__ import annotations

import os
from pathlib import Path

import pytest

from schedview.testing.sample_data import (
    SAMPLE_DATA_DIR_ENV_VAR,
    SAMPLE_PICKLE_ENV_VAR,
    ensure_cached_sample_data,
)

SAMPLE_SCHEDULER_PICKLE = "sample_scheduler.pickle.xz"


def _resolve_sample_data_dir(root_path: Path) -> Path:
    override_dir = os.environ.get(SAMPLE_DATA_DIR_ENV_VAR)
    if override_dir:
        sample_data_dir = Path(override_dir)
    else:
        cache_root = root_path.joinpath(".pytest_cache", "schedview-sample-data")
        sample_data_dir = ensure_cached_sample_data(cache_root)

    if not sample_data_dir.exists():
        raise pytest.UsageError(f"Sample data directory does not exist: {sample_data_dir}")

    sample_pickle = sample_data_dir.joinpath(SAMPLE_SCHEDULER_PICKLE)
    if not sample_pickle.exists():
        raise pytest.UsageError(f"Sample scheduler pickle does not exist: {sample_pickle}")

    os.environ[SAMPLE_DATA_DIR_ENV_VAR] = str(sample_data_dir)
    os.environ[SAMPLE_PICKLE_ENV_VAR] = str(sample_pickle)
    return sample_data_dir


def pytest_configure(config: pytest.Config) -> None:
    _resolve_sample_data_dir(Path(config.rootpath))


@pytest.fixture(scope="session")
def sample_data_dir(pytestconfig: pytest.Config) -> Path:
    return _resolve_sample_data_dir(Path(pytestconfig.rootpath))


@pytest.fixture(scope="session")
def sample_opsim_path(sample_data_dir: Path) -> Path:
    return sample_data_dir.joinpath("sample_opsim.db")


@pytest.fixture(scope="session")
def sample_rewards_path(sample_data_dir: Path) -> Path:
    return sample_data_dir.joinpath("sample_rewards.h5")


@pytest.fixture(scope="session")
def sample_scheduler_pickle_path(sample_data_dir: Path) -> Path:
    return sample_data_dir.joinpath(SAMPLE_SCHEDULER_PICKLE)
