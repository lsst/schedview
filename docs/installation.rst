Installation
============

Installing with ``pip``
-----------------------

Begin by installing ``rubin_sim``.
Note that ``rubin_sim`` is not presently available through ``pypi``, so you will need to use ``conda``, following the instructions on the ``rubin_sim`` documentation:

::

 $ conda create -n rubin-sim -c conda-forge rubin_sim # Create a new environment
 $ conda activate rubin-sim
 $ rs_download_data  # Downloads ~2Gb of data to $RUBIN_SIM_DATA_DIR (~/rubin_sim_data if unset)
 $ conda install -c conda-forge jupyter # Optional install of jupyter

Use ``pip`` to install ``schedview`` itself:

::

 $ pip install schedview

Coming soon: ``conda install -c conda-forge schedview``

For developer use
-----------------

First, get the code by cloning the github project:

::

 $ git clone git@github.com:lsst/schedview.git
 $ cd schedview

Create a ``conda`` environment with the appropriate dependencies, and activate it:

::

 $ conda create -n schedvie
 $ conda activate schedview
 $ conda install -f requirements.txt

Install the (development) ``schedview`` in your new environment:

::

 $ pip install -e .

Some additional packages are required to run the tests.
To install the tests, install the dependenices, then run the tests:

::

 $ conda install -f test-requirements.txt
 $ pytest .

Building the documentation requires the installation of ``documenteer[guide]``:

::

 $ pip install "documenteer[guide]"
 $ cd docs
 $ package-docs build

The root of the local documentation will then be ``docs/_build/html/index.html``.
