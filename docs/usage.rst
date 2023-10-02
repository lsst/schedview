Usage
=====

Running ``scheduler_dashboard``
-------------------------------

Activate the conda environment and start the app:

::

    $ conda activate schedview
    $ scheduler_dashboard

The app will then give you the URL at which you can find the app.

Running ``prenight``
--------------------

Activate the conda environment and start the app:

::

    $ conda activate schedview
    $ prenight

The app will then give you the URL at which you can find the app.

By default, the app will allow the user to select ``opsim`` databas, pickles of
scheduler instances, and rewards data from ``/sdf/group/rubin/web_data/sim-data/schedview``
(if it is being run at the USDF) or the samples directory (elsewhere).
The data directory from which a user can select files can be set on startup:

::

    $ prenight --data_dir /path/to/data/files

Alternately, the user can be allowed to enter arbitrary URLs for these files.
(Note that this is not secure, because it will allow the user to upload
malicious pickles. So, it should only be done when public access to the
dashboard is not possible.) Such a dashboard can be started thus:

::

    $ prenight --insecure

You can also supply an initial set of data files to show on startup:

::

    $ conda activate schedview
    $ prenight --night 2023-10-01 \
    > --opsim_db /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_opsim.db \
    > --scheduler /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_scheduler.pickle.xz \
    > --rewards /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_rewards.h5 \
    > --port 8080
