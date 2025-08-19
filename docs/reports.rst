===================
`schedview` Reports
===================

Introduction
============

`schedview` can be used to generate a any of several reports.
Most of these reports are built from `jupyter` notebooks, either using `Times Square <https://rsp.lsst.io/v/usdfprod/guides/times-square/index.html>`__ or `nbconvert <https://nbconvert.readthedocs.io>`__.

Times Square `schedview` notebooks
==================================

The Times Square schedview notebooks can be found at `https://usdf-rsp.slac.stanford.edu/times-square/github/lsst/schedview_notebooks/nightly/scheduler-nightsum <https://usdf-rsp.slac.stanford.edu/times-square/github/lsst/schedview_notebooks/nightly/scheduler-nightsum>`__.
Times Square reports are generated on demand, but cached after the first time they are executed.
Because the `schedview` notebooks can be slow to execute, this is sometimes incovenient, or can fail altogether.

Pre-generated reports
=====================

To avoid requiring humans to wait for notebooks to be executed, a `cron` job at the USDF uses `nbconvert` to create a set of `html` pages.
The index of reports that are completely public can be found at `https://s3df.slac.stanford.edu/data/rubin/sim-data/schedview/reports/ <https://s3df.slac.stanford.edu/data/rubin/sim-data/schedview/reports/>`__.
Currently, the public reports are limited to a brief nigth summary.

Additional reports, currently requiring logging to the the USDF, can be found at `https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages/ <https://usdf-rsp-int.slac.stanford.edu/schedview-static-pages/>`__.

Hand generation of reports
==========================

The `schedview_notebooks` `github repository <https://github.com/lsst/schedview_notebooks/>`__ contains the notebooks themselves.
Execution of the notebooks requires installation `schedview` and its dependencies, following the `schedview intallation documentation <https://schedview.lsst.io/installation.html>`__.
These can be run directly with a user's `jupyter` instance, or converted to `html` using `nbconvert`.
The notebooks themselves containt documentation about how to do this conversion.
The general pattern followed by these instructions is:

#. Setup the python environment.
#. Assign a set of environment variables. These variables map to the parameters used when the notebooks are run using Times Square.
#. Call `nbconvert` with a command that looks similar to this::

    jupyter nbconvert \
    --to html \
    --execute \
    --no-input \
    --ExecutePreprocessor.kernel_name=python3 \
    --ExecutePreprocessor.startup_timeout=3600 \
    --ExecutePreprocessor.timeout=3600 \
    whatever_notebook.ipynb
