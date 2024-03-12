Installation
============

Installing with ``conda``
-------------------------

``schedview`` can be installed using ``conda``.
If you want to add it to an existing ``conda`` environment::

  $ conda install -c conda-forge schedview

or, to use a dedicated environment for ``schedview``::

  $ conda create --name schedview -c conda-forge schedview

``conda`` will take care of installing the needed python module dependencies,
but some of the data needed by some of its dependencies are not installed
automatically by ``conda``.
To download the necessary data, see the data download pages
`for rubin_scheduler <https://rubin-scheduler.lsst.io/data-download.html#data-download>`_
and `for rubin_sim <https://rubin-sim.lsst.io/data-download.html#data-download>`_

Installing with ``pip``
-----------------------

``schedview`` can be installed using ``pip``.
Starting with whatever ``python`` environment you want to use active::

 $ pip install schedview

``pip`` will take care of installing the needed python module dependencies,
but some of the data needed by some of its dependencies are not installed
automatically by ``pip``.
To download the necessary data, see the data download pages
`for rubin_scheduler <https://rubin-scheduler.lsst.io/data-download.html#data-download>`_
and `for rubin_sim <https://rubin-sim.lsst.io/data-download.html#data-download>`_


For developer use
-----------------

First, get the code by cloning the github project::

 $ git clone git@github.com:lsst/schedview.git
 $ cd schedview

Create a ``conda`` environment with the appropriate dependencies, and activate it::

 $ conda create --name schedview -c conda-forge --only-deps schedview
 $ conda activate schedview

Install the (development) ``schedview`` in your new environment::

 $ pip install -e .

Some additional packages are required to run the tests.
To install the tests, install the dependenices, then run the tests::

 $ conda install -f test-requirements.txt
 $ pytest .

Building the documentation requires the installation of ``documenteer[guide]``::

 $ pip install "documenteer[guide]"
 $ cd docs
 $ package-docs build

The root of the local documentation will then be ``docs/_build/html/index.html``.

Using the schedview S3 bucket
-----------------------------

If a user has appropriate credentials, ``schedview`` can read data from an
``S3`` bucket. To have the ``prenight`` dashboard read data from as ``S3``
bucket, a few steps are needed to prepare the environment in which the
dashboard will be run.

First, the bucket credentials with access to the the endpoint and bucket
in which the archive resides need to be added to ``.lsst/aws-credentials.ini``
file in the account that will be running the dashboard.

For the pre-night ``S3`` bucket at the USDF, the endpoint is
``https://s3dfrgw.slac.stanford.edu/`` and the bucket name is
``rubin-scheduler-prenight``. Access to this bucket must be
coordinated with the USDF administrators and the Rubin Observatory
survey scheduling team.

For example, if the USDF ``S3`` bucket is to be used anth the section with
the ``aws_access_key_id`` and ``aws_secret_access_key`` with access to this
endpoint and bucket is ``prenight``, then the following environment variables
need to be set in the process running the dashboard:

::

     $ export S3_ENDPOINT_URL='https://s3dfrgw.slac.stanford.edu/'
     $ export AWS_PROFILE=prenight

The first of these (``S3_ENDPOINT_URL``) might have been set up automatically
for you if you are running on the USDF.
