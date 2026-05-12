from __future__ import annotations

import hashlib
import importlib.resources
import json
import lzma
import os
import pickle
import shutil
import sys
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

SAMPLE_DATA_DIR_ENV_VAR = "SCHEDVIEW_SAMPLE_DATA_DIR"
SAMPLE_PICKLE_ENV_VAR = "SCHED_PICKLE"
_CACHE_SCHEMA_VERSION = 1
_SAMPLE_OPSIM_DB = "sample_opsim.db"
_SAMPLE_REWARDS_H5 = "sample_rewards.h5"
_SAMPLE_SCHEDULER_PICKLE = "sample_scheduler.pickle.xz"
_MANIFEST_JSON = "manifest.json"
_SAMPLE_DATA_FILE_NAMES = (
    _SAMPLE_OPSIM_DB,
    _SAMPLE_REWARDS_H5,
    _SAMPLE_SCHEDULER_PICKLE,
)

__all__ = [
    "SAMPLE_DATA_DIR_ENV_VAR",
    "SAMPLE_PICKLE_ENV_VAR",
    "ensure_cached_sample_data",
    "get_sample_data_path",
    "write_sample_data",
]


def _get_sample_data_dir() -> Path:
    """Return the directory holding sample test data"""
    override_dir = os.environ.get(SAMPLE_DATA_DIR_ENV_VAR)
    if override_dir:
        return Path(override_dir)

    root_package = __package__.split(".")[0]
    return Path(str(importlib.resources.files(root_package).joinpath("data")))



def get_sample_data_path(file_name: str) -> Path:
    """Return the path to a sample test data artifact"""
    return _get_sample_data_dir().joinpath(file_name)



def _default_sample_date() -> str:
    from astropy.time import Time
    from rubin_scheduler.utils import SURVEY_START_MJD

    return Time(SURVEY_START_MJD, format="mjd").iso[:10]



def _configure_generation_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        module="astropy.time",
        message="Numerical value without unit or explicit format passed to TimeDelta, assuming days",
    )
    warnings.filterwarnings(
        "ignore",
        module="healpy",
        message="divide by zero encountered in divide",
    )
    warnings.filterwarnings(
        "ignore",
        module="healpy",
        message="invalid value encountered in multiply",
    )
    warnings.filterwarnings(
        "ignore",
        module="holoviews",
        message="Discarding nonzero nanoseconds in conversion.",
    )
    warnings.filterwarnings(
        "ignore",
        module="rubin_scheduler",
        message="invalid value encountered in arcsin",
    )
    warnings.filterwarnings(
        "ignore",
        module="rubin_scheduler",
        message="All-NaN slice encountered",
    )



def _manifest(date: str | None = None, duration: int | None = None) -> dict[str, object]:
    resolved_date = _default_sample_date() if date is None else date
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    try:
        rubin_scheduler_version = version("rubin-scheduler")
    except PackageNotFoundError:
        rubin_scheduler_version = "unknown"

    try:
        rubin_sim_version = version("rubin-sim")
    except PackageNotFoundError:
        rubin_sim_version = "unknown"

    return {
        "cache_schema_version": _CACHE_SCHEMA_VERSION,
        "python": ".".join(str(part) for part in sys.version_info[:2]),
        "rubin_scheduler": rubin_scheduler_version,
        "rubin_sim": rubin_sim_version,
        "date": resolved_date,
        "duration_hours": duration,
        "generator_source_hash": source_hash,
        "file_names": list(_SAMPLE_DATA_FILE_NAMES),
    }



def write_sample_data(
    opsim_output_path: str | Path,
    scheduler_output_path: str | Path,
    rewards_output_path: str | Path,
    *,
    date: str | None = None,
    duration: int | None = None,
) -> dict[str, Path]:
    """Write sample test data artifacts"""
    from astropy.time import Time
    from rubin_scheduler.scheduler import sim_runner
    from rubin_scheduler.scheduler.example import example_scheduler
    from rubin_scheduler.scheduler.model_observatory import ModelObservatory
    from rubin_scheduler.scheduler.utils import SchemaConverter

    _configure_generation_warnings()

    resolved_date = _default_sample_date() if date is None else date
    opsim_output_path = Path(opsim_output_path)
    scheduler_output_path = Path(scheduler_output_path)
    rewards_output_path = Path(rewards_output_path)

    for output_path in (opsim_output_path, scheduler_output_path, rewards_output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    observatory = ModelObservatory()
    evening_mjd = Time(resolved_date).mjd
    this_night = np.floor(observatory.almanac.sunsets["sunset"] + observatory.site.longitude / 360) == evening_mjd
    sim_start_mjd = observatory.almanac.sunsets[this_night]["sun_n12_setting"][0]
    sim_end_mjd = observatory.almanac.sunsets[this_night]["sunrise"][0]
    sim_duration = duration / 24.0 if duration is not None else sim_end_mjd - sim_start_mjd

    observatory = ModelObservatory(mjd_start=sim_start_mjd)
    scheduler = example_scheduler(mjd_start=sim_start_mjd)
    scheduler.keep_rewards = True

    observatory, scheduler, observations, reward_df, obs_rewards = sim_runner(
        observatory,
        scheduler,
        sim_start_mjd=sim_start_mjd,
        sim_duration=sim_duration,
        record_rewards=True,
    )

    SchemaConverter().obs2opsim(observations, filename=str(opsim_output_path))

    with lzma.open(scheduler_output_path, "wb", format=lzma.FORMAT_XZ) as pickle_io:
        pickle.dump((scheduler, scheduler.conditions), pickle_io)

    reward_df.to_hdf(str(rewards_output_path), key="reward_df")
    obs_rewards.to_hdf(str(rewards_output_path), key="obs_rewards")

    return {
        _SAMPLE_OPSIM_DB: opsim_output_path,
        _SAMPLE_SCHEDULER_PICKLE: scheduler_output_path,
        _SAMPLE_REWARDS_H5: rewards_output_path,
    }



def _generate_sample_data_dir(
    output_dir: str | Path,
    *,
    date: str | None = None,
    duration: int | None = None,
) -> Path:
    """Generate a complete sample test data directory"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_sample_data(
        output_dir.joinpath(_SAMPLE_OPSIM_DB),
        output_dir.joinpath(_SAMPLE_SCHEDULER_PICKLE),
        output_dir.joinpath(_SAMPLE_REWARDS_H5),
        date=date,
        duration=duration,
    )
    return output_dir



def ensure_cached_sample_data(
    cache_root: str | Path,
    *,
    date: str | None = None,
    duration: int | None = None,
) -> Path:
    """Return a cached directory of generated sample test data"""
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    manifest = _manifest(date=date, duration=duration)
    manifest_json = json.dumps(manifest, sort_keys=True)
    digest = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()[:16]
    cache_dir = cache_root.joinpath(digest)
    manifest_path = cache_dir.joinpath(_MANIFEST_JSON)
    required_paths = [cache_dir.joinpath(file_name) for file_name in _SAMPLE_DATA_FILE_NAMES]

    if manifest_path.exists() and all(path.exists() for path in required_paths):
        cached_manifest = json.loads(manifest_path.read_text())
        if cached_manifest == manifest:
            return cache_dir

    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    _generate_sample_data_dir(
        cache_dir,
        date=manifest["date"],
        duration=duration,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return cache_dir
