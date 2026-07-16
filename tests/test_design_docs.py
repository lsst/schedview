"""Tests for RST design documents under design/."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

DESIGN_DIR = Path(__file__).parent.parent / "design"
RST_FILES = sorted(DESIGN_DIR.rglob("*.rst"))

# rst2html calls locale.setlocale(locale.LC_ALL, '') on startup, which fails
# if the environment's locale (e.g. en_US.UTF-8) isn't installed on the host.
# Force a locale that is always available so the test doesn't depend on the
# host's locale configuration.
_RST_ENV = {**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}


def _rst_id(rst_path):
    """Return a short test ID for a design-doc path."""
    return str(rst_path.relative_to(DESIGN_DIR))


@pytest.mark.design
@pytest.mark.parametrize("rst_file", RST_FILES, ids=_rst_id)
def test_rst_valid(rst_file):
    """Verify RST file parses without warnings."""
    result = subprocess.run(
        ["rst2html", "--halt=warning", str(rst_file), "/dev/null"],
        capture_output=True,
        text=True,
        env=_RST_ENV,
    )
    assert result.returncode == 0, f"RST validation failed for {rst_file.name}:\n{result.stderr}"


@pytest.mark.design
@pytest.mark.parametrize("rst_file", RST_FILES, ids=_rst_id)
def test_rst_doctests(rst_file):
    """Verify all doctests in RST file pass."""
    result = subprocess.run(
        [sys.executable, "-m", "doctest", str(rst_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Doctests failed for {rst_file.name}:\n" f"{result.stdout}\n{result.stderr}"
    )
