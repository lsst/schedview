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

Note: at present, there are some dependencies which are not listed in the
conda recipe, either because there is no conda package or we are determining
whether it is safe to include them for installation in an LSST Stack metapackage.
To add these additional packages, please install the following into your environment::

  $ pip install lsst-resources
  $ conda install -c conda-forge lsst-efd-client


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

 $ conda create --channel conda-forge --name rubin_sim --file requirements.txt python=3.11
 $ conda activate schedview

Install the (development) ``schedview`` in your new environment::

 $ pip install -e . --no-deps

Some additional packages are required to run the tests.
To install the tests, install the dependenices::

 $ conda install -c conda-forge -f test-requirements.txt

Some tests use ``playwright``, but the conda-forge package for ``playwright``
is presently broken. You can install it either from the microsoft channel::

 $ conda install -c microsoft playwright

or with pip::

 $ pip install playwright

Then use playwright itself to install some things it depends on::

 $ playwright install
 $ playwright install-deps

Finally, run the tests::

 $ pytest .

By default, playwright tests are disabled. You can enable them thus:

$ ENABLE_PLAYWRIGHT_TESTS=1 pytest .

Building the documentation requires the installation of ``documenteer[guide]``::

 $ pip install "documenteer[guide]"
 $ cd docs
 $ package-docs build

The root of the local documentation will then be ``docs/_build/html/index.html``.

Using the schedview S3 bucket
-----------------------------

``schedview`` can read data from an S3 bucket.
To have the prenight dashboard read data from as S3 bucket, a few steps are
needed to prepare the environment in which the dashboard will be run.

First, a couple of additional python modules need to be installed::

 $ conda install -c conda-forge boto3 botocore

For the pre-night S3 bucket at the USDF, the endpoint is
``https://s3dfrgw.slac.stanford.edu/`` and the bucket name is
``rubin:rubin-scheduler-prenight``.

Users running in the notebook aspect of the USDF RSP will have a default
credential in their ``~/.lsst/aws-credentials.ini`` file sufficient to
read this bucket. (Read access is all that is used by ``schedview``.
Write access to this bucket must be coordinated with the USDF administrators
and the Rubin Observatory survey scheduling team.)

A few environment variables need to be set in the process running the
dashboard::

 $ export S3_ENDPOINT_URL='https://s3dfrgw.slac.stanford.edu/'
 $ export LSST_DISABLE_BUCKET_VALIDATION=1

The first of these (``S3_ENDPOINT_URL``) might have been set up automatically
for you if you are running on the USDF.

If you are not using the default credential at the USDF, you may also need
to set your environment to point to the correct one, for example::

$ export AWS_PROFILE=prenight
