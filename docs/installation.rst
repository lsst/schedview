Installation
============

Installing dashboards
---------------------

First, get the code by cloning the github project:

    $ git clone git@github.com:lsst/schedview.git

Create a `conda` environment with the appropriate dependencies, and activate it.
If you are running the `metric_maps` application, use the `conda` environment
file that includes a recent version of `rubin_sim`:

    $ conda env create -f environment.yaml
    $ conda activate schedview

Install the (development) `schedview` in your new environment:

    $ pip install -e .

Run the tests:

    $ pytest


Building Documentation
----------------------

Online documentation require the installation of `documenteer[guide]`:

::

 pip install "documenteer[guide]"
 cd docs
 make clean
 make html


The root of the local documentation will then be `docs/_build/html/index.html`.
