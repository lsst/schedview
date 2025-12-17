Usage
=====

Running ``scheduler_dashboard``
-------------------------------

Begin by activating the conda environment::

    $ conda activate schedview

There are three ways to start the dashboard, depending on what you want to use
as the source of data.
One way is for users to enter arbitrary URLs or file paths from which to load
the data. **This is insecure,** because users can point the dashboard to malicious
snapshots. It is, however, much more flexible in a secure environment::

    $ scheduler_dashboard --data-from-urls

Alternately, the dashboard can be started with a flag to only allow users to
load data from a pre-specified directory on the host running the dashboard::

    $ scheduler_dashboard --data_dir /where/the/snapshot/pickles/are

Finally, if the dashboard is running at the USDF or another LFA facility, data can
be loaded from an S3 bucket that is already preset in the dashboard. The dashboard
will retrieve a list of snapshots for a selected night.

To start the dashbaord in LFA mode::

     $ scheduler_dashboard --lfa

In each case, the app will then give you the URL at which you can find the app.
