============================================================
Design: Pytest integration for design documents
============================================================

Overview
--------

Add automated testing for reStructuredText design documents under the
``design/`` directory.  Two checks are performed on each ``.rst`` file:

1. **RST validity** — verifies the document parses without warnings using
   ``rst2html --halt=warning``.
2. **Doctest correctness** — verifies all embedded ``>>>`` code blocks
   execute successfully using ``python -m doctest``.

These tests are excluded from normal test runs (``pytest tests``) via a
custom ``design`` marker, and run only when explicitly requested
(``pytest -m design tests``).


Motivation
----------

The design documents in ``design/SP-3225/`` contain both prose and
executable code examples (doctests) that serve as white-box verification
of the implementation.  Without automated checking:

- RST syntax errors (unclosed inline literals, bad indentation) go
  unnoticed until someone tries to render the document.
- Doctests silently rot as the underlying code evolves.

Integrating these checks into the pytest suite provides a single command
to verify document quality, while keeping them out of the default test
run (which focuses on the library itself).


Design Decisions
----------------

**Why a marker rather than a separate test directory?**

Placing the test module in ``tests/test_design_docs.py`` keeps all tests
discoverable through the existing ``tests/`` directory.  The ``design``
marker plus a ``pytest_collection_modifyitems`` hook gives us skip-by-default
behavior without needing ``addopts`` changes or a separate ``testpaths``
entry.

**Why ``pytest_collection_modifyitems`` instead of ``addopts = "-m not design"``?**

Putting ``-m "not design"`` in ``addopts`` conflicts with explicit
``-m design`` on the command line — pytest does not merge marker
expressions, and the interaction between the two ``-m`` flags is
undefined (in practice, one shadows the other depending on pytest
version).  The ``pytest_collection_modifyitems`` hook cleanly detects
whether the user supplied an explicit ``-m`` expression and only skips
design tests when no marker filter was requested.

**Why ``subprocess.run`` rather than importing docutils/doctest directly?**

Using subprocess ensures each RST file is validated in isolation with the
same command-line tools a developer would use manually.  It also avoids
importing docutils internals or managing doctest state across files.

**Why parametrize over discovered files?**

Using ``pytest.mark.parametrize`` with a glob of ``design/**/*.rst``
means new design documents are automatically picked up without editing
the test file.  A named helper function (``_rst_id``) generates short
test IDs (e.g. ``test_rst_valid[SP-3225/smallsum.rst]``), making
failures easy to locate.


Changes Required
----------------

Three files are modified or created:

1. ``pyproject.toml`` — register the ``design`` marker.
2. ``tests/conftest.py`` — add ``pytest_collection_modifyitems`` hook.
3. ``tests/test_design_docs.py`` — the new test module (created).


Change 1: ``pyproject.toml``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the ``markers`` list to ``[tool.pytest.ini_options]``:

.. code-block:: toml

    [tool.pytest.ini_options]
    addopts = "--ignore-glob=*/version.py --ignore-glob=*data_dir/*"
    testpaths = "."
    asyncio_default_fixture_loop_scope="function"
    markers = [
        "design: tests for RST design documents (skipped by default)",
    ]

This suppresses the ``PytestUnknownMarkWarning`` that would otherwise
appear when pytest encounters ``@pytest.mark.design``.


Change 2: ``tests/conftest.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a ``pytest_collection_modifyitems`` hook that skips design-marked
tests when no explicit ``-m`` expression is provided:

.. code-block:: python

    def pytest_collection_modifyitems(config, items):
        """Skip design-doc tests unless an explicit marker expression is given."""
        if not config.getoption("-m"):
            skip_design = pytest.mark.skip(
                reason="design tests not selected (use -m design)"
            )
            for item in items:
                if "design" in item.keywords:
                    item.add_marker(skip_design)

**Behavior:**

- ``pytest tests`` → design tests are **skipped** (shown as ``SKIPPED``
  in output with a reason message).
- ``pytest -m design tests`` → **only** design tests run (non-design
  tests are deselected by pytest's marker filtering).
- ``pytest -m "design or not design" tests`` → **all** tests run
  (both design and non-design).


Change 3: ``tests/test_design_docs.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

New test module with two parametrized test functions:

.. code-block:: python

    """Tests for RST design documents under design/."""

    import subprocess
    import sys
    from pathlib import Path

    import pytest

    DESIGN_DIR = Path(__file__).parent.parent / "design"
    RST_FILES = sorted(DESIGN_DIR.rglob("*.rst"))


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
        )
        assert result.returncode == 0, (
            f"RST validation failed for {rst_file.name}:\n{result.stderr}"
        )


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
            f"Doctests failed for {rst_file.name}:\n"
            f"{result.stdout}\n{result.stderr}"
        )


Usage
-----

Run design document tests only:

.. code-block:: bash

    pytest -m design tests

Run all tests including design:

.. code-block:: bash

    pytest -m "design or not design" tests

Normal test run (design tests skipped):

.. code-block:: bash

    pytest tests


Expected Output
---------------

When design tests are skipped (default):

.. code-block:: text

    tests/test_design_docs.py::test_rst_valid[SP-3225/designtest.rst] SKIPPED
    tests/test_design_docs.py::test_rst_valid[SP-3225/linktablestats.rst] SKIPPED
    tests/test_design_docs.py::test_rst_valid[SP-3225/smallsum.rst] SKIPPED
    tests/test_design_docs.py::test_rst_valid[SP-3225/visitcache.rst] SKIPPED
    ...

When design tests are selected:

.. code-block:: text

    tests/test_design_docs.py::test_rst_valid[SP-3225/designtest.rst] PASSED
    tests/test_design_docs.py::test_rst_valid[SP-3225/linktablestats.rst] PASSED
    tests/test_design_docs.py::test_rst_valid[SP-3225/smallsum.rst] PASSED
    tests/test_design_docs.py::test_rst_valid[SP-3225/visitcache.rst] PASSED
    tests/test_design_docs.py::test_rst_doctests[SP-3225/designtest.rst] PASSED
    tests/test_design_docs.py::test_rst_doctests[SP-3225/linktablestats.rst] PASSED
    tests/test_design_docs.py::test_rst_doctests[SP-3225/smallsum.rst] PASSED
    tests/test_design_docs.py::test_rst_doctests[SP-3225/visitcache.rst] PASSED


Dependencies
------------

- ``docutils`` (provides ``rst2html``; already installed in the venv as a
  transitive dependency)
- ``pytest`` (already a test dependency)
- No new package installations required.


Edge Cases
----------

**No RST files found**: If ``design/`` is empty or absent,
``RST_FILES`` will be an empty list and pytest will report "no tests ran"
for the parametrized functions (``collected 0 items``).  This is harmless.

**RST files without doctests**: Files that contain no ``>>>`` lines will
pass ``python -m doctest`` with exit code 0 (no tests collected, no
failures).

**Long-running doctests**: Since doctests are run via subprocess, each
file runs in its own process.  Slow imports (e.g., ``Almanac``) will
add wall-clock time.  The design tests are excluded from default runs
specifically to avoid this overhead in routine development.
