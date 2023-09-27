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

You can also supply an initial set of data files to show on startup:

::

    $ conda activate schedview
    $ prenight --night 2023-10-01 \
    > --opsim_db /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_opsim.db \
    > --scheduler /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_scheduler.pickle.xz \
    > --rewards /sdf/data/rubin/user/neilsen/devel/schedview/schedview/data/sample_rewards.h5 \
    > --port 8080
