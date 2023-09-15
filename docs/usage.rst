Usage
=====

Running `sched_maps`
--------------------

Activate the environment, and start the `bokeh` app. If `SCHEDVIEW_DIR` is the
directory into which you cloned the `schedview` github repository, then

::

    $ conda activate schedview
    $ bokeh serve ${SCHEDVIEW_DIR}/schedview/app/sched_maps

The app will then give you the URL at which you can find the app.

Running `prenight`
------------------

Activate the environment, and start the `bokeh` app. If `SCHEDVIEW_DIR` is the
directory into which you cloned the `schedview` github repository, then:

::

    $ conda activate schedview
    $ python ${SCHEDVIEW_DIR}/schedview/app/prenight/prenight.py
