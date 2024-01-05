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

Using the schedview S3 bucket
-----------------------------

To use the ``schedview`` ``S3`` bucket, a few steps are needed to prepare the
environment in which the dashboard will be run.

First, the bucket credentials with access to the ``rubin-scheduler-prenight``
bucket at the endpoint ``https://s3dfrgw.slac.stanford.edu/`` need to be
added to ``.lsst/aws-credentials.ini`` in the account that will be running
the dashboard.

If the section with the ``aws_access_key_id`` and
``aws_secret_access_key`` with access to this endpoint and bucket is
``prenight``, then the following environment variables need to be set
in the process running the dashboard:

::

     $ export S3_ENDPOINT_URL='https://s3dfrgw.slac.stanford.edu/'
     $ export AWS_PROFILE=prenight

The first of these (``S3_ENDPOINT_URL``) might have been set up automatically
for you if you are running on the USDF.
