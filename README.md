# schedview

[![pypi](https://img.shields.io/pypi/v/schedview.svg)](https://pypi.org/project/schedview/)
 [![Conda Version](https://img.shields.io/conda/vn/conda-forge/schedview.svg)](https://anaconda.org/conda-forge/schedview) <br>
[![Run CI](https://github.com/lsst/schedview/actions/workflows/test_and_build.yaml/badge.svg)](https://github.com/lsst/schedview/actions/workflows/test_and_build.yaml)
[![codecov](https://codecov.io/gh/lsst/schedview/branch/main/graph/badge.svg?token=2BUBL8R9RH)](https://codecov.io/gh/lsst/schedview)

The `schedview` module provides tools for visualizing Rubin Observatory scheduler behaviour and Rubin Observatory/LSST survey status, including:

- A collection of functions, eacho of which creates an independent visualization of some aspect of scheduler behaviour, state, or surve progress. These functions may be used in `jupyter` notebooks or other python applications, or combined into dashboards or other higher level applications.
- A handful of dashboard applications that collect relevant visualizations into sets suitable for specific use cases.
