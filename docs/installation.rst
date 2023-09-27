Installation
============

Installing with ``pip``
-----------------------

Use pip install:

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
