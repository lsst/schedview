Architecture
============

This documentation was generated from a jupyter notebook,
``architecture.ipynb``, which can be found in the ``notebooks``
directory of ``schedview``.

Automatically format code in this notebook:

.. code:: ipython3

    %load_ext lab_black

Introduction
------------

The ``schedview`` module organizes code used to create scheduler
visualizations into four submodules corresponding to different stages in
transforming the data from a raw reference to a source into a useful
visualization. These four stages are:

-  collection, which obtains the data from whatever resources are
   required;
-  computation, which transforms the data into values to be directly
   represented in the visualizatios;
-  plotting, which generates visualization objects; and
-  dashboard generation, which collects and displays visualizations in a
   web application

This notebook walks through the process of creating a visualization, one
stage at a time.

Collection
----------

Code in the ``schedview.collect`` submodule retrieves the data to be
visualized from wherever they originate. Typically, functions in
``schedview.collect`` take references to resources (e.g. file names or
URLs) as arguments and return python objects.

For example, consider the function below, which reads orbital elements
for minor planets from a file using the ``skyfield`` module:

.. code:: ipython3

    import skyfield.api
    import skyfield.data.mpc


    def read_minor_planet_orbits(file_name):
        with skyfield.api.load.open(file_name) as file_io:
            minor_planets = skyfield.data.mpc.load_mpcorb_dataframe(file_io)
        return minor_planets

Take a look at what it does:

.. code:: ipython3

    file_name = "mpcorb_sample_big.dat"
    minor_planet_orbits = read_minor_planet_orbits(file_name)
    minor_planet_orbits




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }

        .dataframe tbody tr th {
            vertical-align: top;
        }

        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>designation_packed</th>
          <th>magnitude_H</th>
          <th>magnitude_G</th>
          <th>epoch_packed</th>
          <th>mean_anomaly_degrees</th>
          <th>argument_of_perihelion_degrees</th>
          <th>longitude_of_ascending_node_degrees</th>
          <th>inclination_degrees</th>
          <th>eccentricity</th>
          <th>mean_daily_motion_degrees</th>
          <th>...</th>
          <th>observations</th>
          <th>oppositions</th>
          <th>observation_period</th>
          <th>rms_residual_arcseconds</th>
          <th>coarse_perturbers</th>
          <th>precise_perturbers</th>
          <th>computer_name</th>
          <th>hex_flags</th>
          <th>designation</th>
          <th>last_observation_date</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>00001</td>
          <td>3.33</td>
          <td>0.15</td>
          <td>K239D</td>
          <td>60.07881</td>
          <td>73.42179</td>
          <td>80.25496</td>
          <td>10.58688</td>
          <td>0.078913</td>
          <td>0.214107</td>
          <td>...</td>
          <td>7283</td>
          <td>123</td>
          <td>1801-2023</td>
          <td>0.65</td>
          <td>M-v</td>
          <td>30k</td>
          <td>MPCLINUX</td>
          <td>0000</td>
          <td>(1) Ceres</td>
          <td>20230321</td>
        </tr>
        <tr>
          <th>1</th>
          <td>00002</td>
          <td>4.12</td>
          <td>0.15</td>
          <td>K239D</td>
          <td>40.59806</td>
          <td>310.87290</td>
          <td>172.91881</td>
          <td>34.92584</td>
          <td>0.230229</td>
          <td>0.213774</td>
          <td>...</td>
          <td>8862</td>
          <td>121</td>
          <td>1804-2023</td>
          <td>0.59</td>
          <td>M-c</td>
          <td>28k</td>
          <td>MPCLINUX</td>
          <td>0000</td>
          <td>(2) Pallas</td>
          <td>20230603</td>
        </tr>
        <tr>
          <th>2</th>
          <td>00003</td>
          <td>5.16</td>
          <td>0.15</td>
          <td>K239D</td>
          <td>37.02310</td>
          <td>247.73792</td>
          <td>169.83920</td>
          <td>12.99055</td>
          <td>0.256213</td>
          <td>0.226004</td>
          <td>...</td>
          <td>7450</td>
          <td>113</td>
          <td>1804-2023</td>
          <td>0.63</td>
          <td>M-v</td>
          <td>3Ek</td>
          <td>MPCLINUX</td>
          <td>0000</td>
          <td>(3) Juno</td>
          <td>20230210</td>
        </tr>
        <tr>
          <th>3</th>
          <td>00004</td>
          <td>3.22</td>
          <td>0.15</td>
          <td>K239D</td>
          <td>169.35183</td>
          <td>151.66223</td>
          <td>103.71002</td>
          <td>7.14218</td>
          <td>0.089449</td>
          <td>0.271522</td>
          <td>...</td>
          <td>7551</td>
          <td>110</td>
          <td>1821-2023</td>
          <td>0.63</td>
          <td>M-p</td>
          <td>18k</td>
          <td>MPCLINUX</td>
          <td>0000</td>
          <td>(4) Vesta</td>
          <td>20230814</td>
        </tr>
      </tbody>
    </table>
    <p>4 rows × 23 columns</p>
    </div>



This code doesn’t actually *do* anything to the data: it just retrieves
it. When using ``schedview`` at sites that require different access
methods, different implementations of the ``collect`` stage will be
needed. If different sites with different access methods need to do the
same cleaning, selection, or computation on the data, the implementation
of such code within the ``collection`` submodule will hinder code reuse.

Computation
-----------

In instances where the data cannot be visualized directly as returned
from the data source, any processing should be done using the
``schedview.compute`` submodule.

For example, let’s say we want to plot the positions of the minor
planets whose orbital elements we loaded in the collection example
above. We are not interested in the orbital elements directly, but
rather the positions, so we need to actually derive the one from the
other. So, we create a function in the ``schedview.compute`` submodule
that drives the code to do the computation, and create an object
suitable for passing as input to whatever module we are using for
creating plots. (In this case, that’s ``bokeh``, but it could as easily
have been ``matplotlib``.)

.. code:: ipython3

    import astropy.units as u
    from astropy.time import Time, TimeDelta
    from astropy.timeseries import TimeSeries
    import skyfield.api
    import skyfield.data.mpc
    from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
    import bokeh.models


    def compute_minor_planet_positions(
        minor_planet_orbits, start_mjd, end_mjd, time_step=7
    ):
        # Convert input fields into object appropriate for skyfield
        timescale = skyfield.api.load.timescale()
        start_ts = timescale.from_astropy(Time(start_mjd, format="mjd"))
        end_ts = timescale.from_astropy(Time(end_mjd, format="mjd"))
        n_samples = int((1 + end_mjd - start_mjd) / time_step)
        sample_times = timescale.linspace(start_ts, end_ts, n_samples)

        ephemeris = skyfield.api.load("de421.bsp")
        sun = ephemeris["sun"]

        position_data = {"designation": [], "mjd": [], "ra": [], "decl": [], "distance": []}
        for _, orbit in minor_planet_orbits.iterrows():
            orbit_rel_sun = skyfield.data.mpc.mpcorb_orbit(orbit, timescale, GM_SUN)
            minor_planet = sun + orbit_rel_sun
            for sample_time in sample_times:
                ra, decl, distance = (
                    ephemeris["earth"].at(sample_time).observe(minor_planet).radec()
                )
                position_data["designation"].append(orbit["designation"])
                position_data["mjd"].append(sample_time.to_astropy().mjd)
                position_data["ra"].append(ra._degrees)
                position_data["decl"].append(decl._degrees)
                position_data["distance"].append(distance.au)

        position_ds = bokeh.models.ColumnDataSource(position_data)

        return position_ds

Take a look at what it does:

.. code:: ipython3

    position_ds = compute_minor_planet_positions(minor_planet_orbits, 60200, 60366, 1)
    position_ds.to_df()




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }

        .dataframe tbody tr th {
            vertical-align: top;
        }

        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th>designation</th>
          <th>mjd</th>
          <th>ra</th>
          <th>decl</th>
          <th>distance</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>0</th>
          <td>(1) Ceres</td>
          <td>60200.000801</td>
          <td>208.460906</td>
          <td>-6.151262</td>
          <td>3.373882</td>
        </tr>
        <tr>
          <th>1</th>
          <td>(1) Ceres</td>
          <td>60201.000801</td>
          <td>208.830744</td>
          <td>-6.329553</td>
          <td>3.382607</td>
        </tr>
        <tr>
          <th>2</th>
          <td>(1) Ceres</td>
          <td>60202.000801</td>
          <td>209.201817</td>
          <td>-6.507387</td>
          <td>3.391235</td>
        </tr>
        <tr>
          <th>3</th>
          <td>(1) Ceres</td>
          <td>60203.000801</td>
          <td>209.574111</td>
          <td>-6.684750</td>
          <td>3.399765</td>
        </tr>
        <tr>
          <th>4</th>
          <td>(1) Ceres</td>
          <td>60204.000801</td>
          <td>209.947612</td>
          <td>-6.861627</td>
          <td>3.408197</td>
        </tr>
        <tr>
          <th>...</th>
          <td>...</td>
          <td>...</td>
          <td>...</td>
          <td>...</td>
          <td>...</td>
        </tr>
        <tr>
          <th>663</th>
          <td>(4) Vesta</td>
          <td>60362.000801</td>
          <td>81.371339</td>
          <td>23.180175</td>
          <td>2.035636</td>
        </tr>
        <tr>
          <th>664</th>
          <td>(4) Vesta</td>
          <td>60363.000801</td>
          <td>81.475208</td>
          <td>23.222025</td>
          <td>2.047772</td>
        </tr>
        <tr>
          <th>665</th>
          <td>(4) Vesta</td>
          <td>60364.000801</td>
          <td>81.586028</td>
          <td>23.263744</td>
          <td>2.059969</td>
        </tr>
        <tr>
          <th>666</th>
          <td>(4) Vesta</td>
          <td>60365.000801</td>
          <td>81.703711</td>
          <td>23.305317</td>
          <td>2.072222</td>
        </tr>
        <tr>
          <th>667</th>
          <td>(4) Vesta</td>
          <td>60366.000801</td>
          <td>81.828170</td>
          <td>23.346729</td>
          <td>2.084530</td>
        </tr>
      </tbody>
    </table>
    <p>668 rows × 5 columns</p>
    </div>



``schedview.compute`` is not intended to hold processing code of general
interest, but rather computation specific to the creation of scheduler
visualizations.

In the example above, the function itself did not implement the orbital
calculations itself, but rather called the functionality in
``skyfield``.

Even in instances specific to Rubin Observatory, the computation may be
better collected in other modules (e.g. ``rubin_sim``) or in their own,
and then called by a thin driver in ``schedview.compute``.

When the computations are time-consuming, it may be better use separate
processes to generate data products independenty of ``schedview``, and
then load these derived data products using tools in
``schedview.collect``.

Plotting
--------

Functions in the ``schedview.plot`` submodule create instances of
visualization objects from the data, as provided either by the
``schedview.collect`` or ``schedview.compute`` (when necessary)
submodules.

These “visualization objects” can be anything that can be directly
rendered in a jupyter notebook or by panel in a dashboard, including
``matplotlib`` figures, ``bokeh`` plots, plain HTML, ``png`` images, and
many others.

This example creates a simple plot of the minor planet data, as
generated above:

.. code:: ipython3

    import bokeh.plotting
    import bokeh.palettes
    import bokeh.transform
    import numpy as np


    def map_minor_planet_positions(position_ds):
        figure = bokeh.plotting.figure()

        minor_planet_designations = np.unique(position_ds.data["designation"])
        cmap = bokeh.transform.factor_cmap(
            "designation",
            palette=bokeh.palettes.Category20[len(minor_planet_designations)],
            factors=minor_planet_designations,
        )

        figure.scatter(
            "ra", "decl", color=cmap, legend_field="designation", source=position_ds
        )
        figure.title = "Select minor planet positions"
        figure.yaxis.axis_label = "Declination (degrees)"
        figure.xaxis.axis_label = "R.A. (degrees)"

        return figure

Once again, we can display this directly within our notebook:

.. code:: ipython3

    import bokeh.io

    # Add the jupyter extension that supports display of bokeh figures
    # This only needs to be done once, typically at the top of a notebook.
    bokeh.io.output_notebook()

    figure = map_minor_planet_positions(position_ds)
    bokeh.io.show(figure)



.. raw:: html

    <style>
            .bk-notebook-logo {
                display: block;
                width: 20px;
                height: 20px;
                background-image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEgAACxIB0t1+/AAAABx0RVh0U29mdHdhcmUAQWRvYmUgRmlyZXdvcmtzIENTNui8sowAAAOkSURBVDiNjZRtaJVlGMd/1/08zzln5zjP1LWcU9N0NkN8m2CYjpgQYQXqSs0I84OLIC0hkEKoPtiH3gmKoiJDU7QpLgoLjLIQCpEsNJ1vqUOdO7ppbuec5+V+rj4ctwzd8IIbbi6u+8f1539dt3A78eXC7QizUF7gyV1fD1Yqg4JWz84yffhm0qkFqBogB9rM8tZdtwVsPUhWhGcFJngGeWrPzHm5oaMmkfEg1usvLFyc8jLRqDOMru7AyC8saQr7GG7f5fvDeH7Ej8CM66nIF+8yngt6HWaKh7k49Soy9nXurCi1o3qUbS3zWfrYeQDTB/Qj6kX6Ybhw4B+bOYoLKCC9H3Nu/leUTZ1JdRWkkn2ldcCamzrcf47KKXdAJllSlxAOkRgyHsGC/zRday5Qld9DyoM4/q/rUoy/CXh3jzOu3bHUVZeU+DEn8FInkPBFlu3+nW3Nw0mk6vCDiWg8CeJaxEwuHS3+z5RgY+YBR6V1Z1nxSOfoaPa4LASWxxdNp+VWTk7+4vzaou8v8PN+xo+KY2xsw6une2frhw05CTYOmQvsEhjhWjn0bmXPjpE1+kplmmkP3suftwTubK9Vq22qKmrBhpY4jvd5afdRA3wGjFAgcnTK2s4hY0/GPNIb0nErGMCRxWOOX64Z8RAC4oCXdklmEvcL8o0BfkNK4lUg9HTl+oPlQxdNo3Mg4Nv175e/1LDGzZen30MEjRUtmXSfiTVu1kK8W4txyV6BMKlbgk3lMwYCiusNy9fVfvvwMxv8Ynl6vxoByANLTWplvuj/nF9m2+PDtt1eiHPBr1oIfhCChQMBw6Aw0UulqTKZdfVvfG7VcfIqLG9bcldL/+pdWTLxLUy8Qq38heUIjh4XlzZxzQm19lLFlr8vdQ97rjZVOLf8nclzckbcD4wxXMidpX30sFd37Fv/GtwwhzhxGVAprjbg0gCAEeIgwCZyTV2Z1REEW8O4py0wsjeloKoMr6iCY6dP92H6Vw/oTyICIthibxjm/DfN9lVz8IqtqKYLUXfoKVMVQVVJOElGjrnnUt9T9wbgp8AyYKaGlqingHZU/uG2NTZSVqwHQTWkx9hxjkpWDaCg6Ckj5qebgBVbT3V3NNXMSiWSDdGV3hrtzla7J+duwPOToIg42ChPQOQjspnSlp1V+Gjdged7+8UN5CRAV7a5EdFNwCjEaBR27b3W890TE7g24NAP/mMDXRWrGoFPQI9ls/MWO2dWFAar/xcOIImbbpA3zgAAAABJRU5ErkJggg==);
            }
        </style>
        <div>
            <a href="https://bokeh.org" target="_blank" class="bk-notebook-logo"></a>
            <span id="dad70ae4-57c7-449f-b94a-80e0e268ee45">Loading BokehJS ...</span>
        </div>






.. raw:: html


    <div id="bc3312ff-955b-46cc-b8cf-5a9f9f6123e2" data-root-id="p1004" style="display: contents;"></div>





The ``schedview`` module holds plotting tools for specific instances of
plots useful for studying the scheduler or survey progress.

As was the case for functions in the ``schedview.compute`` submodule,
functionality that is of interest beyond the scheduler should be
extracted into a separate module. The ``uranography`` module is an
example of where this has already been done.

Dashboard applications
----------------------

Together, a developer can use functions supplied by the
``schedview.collect``, ``schedview.compute``, and ``schedview.plot``
submodules to build plots in jupyter notebooks. Using ``schedview`` in
this maximizes flexibility, allowing bespoke or alternate collection and
processing between or instead of functions supplied by ``schedview``,
and the plots themselves can be extended and customized beyond what
schedview provides using the relevant plotting libraries (``bokeh`` or
``matplotlib``).

Often, though, standardized dashboards that show a set of visualizations
easily is more useful, even at the expense of the full flexibility of a
jupyter notebook.

For this, dashboard applications can be created the ``schedview.app``
submodule.

The suggested tool for building such applications is the creation of a
``param.Parameterized`` class displayed through a ``panel`` application.

The class definition of a ``param.Parameterized`` subclass encodes
dependencies between user supplied parameters, stages of processing, and
the visualization ultimately produced.

The ``panel`` and ``param`` documentation provides more complete
explanation and tutorials. Note that there are alternate approaches to
using ``panel`` to generate dashboards; this approach is covered by the
`“Declare UIs with Declarative
API” <https://panel.holoviz.org/how_to/param/index.html>`__ section of
the ``panel`` documentation.

A full explanation of the ``panel``\ ’s declarative API is beyond the
scope of this notebook, but ``SimpleSampleDashboard`` class below gives
a simple example of how it works.

.. code:: ipython3

    import param
    import panel as pn


    class SimpleSampleDashboard(param.Parameterized):
        orbit_filename = param.FileSelector(
            default="./mpcorb_sample_big.dat",
            path="./mpcorb_*.dat",
            doc="Data file with orbit parameters",
            label="Orbit data file",
        )

        start_mjd = param.Number(
            default=60200,
            doc="Modified Julian Date of start of date window",
            label="Start MJD",
        )

        end_mjd = param.Number(
            default=60565, doc="Modified Julian Date of end of date window", label="End MJD"
        )

        orbits = param.Parameter()

        positions = param.Parameter()

        @param.depends("orbit_filename", watch=True)
        def update_orbits(self):
            if self.orbit_filename is None:
                print("No file supplied, not loading orbits")
                return

            print("Updating orbits")
            self.orbits = read_minor_planet_orbits(self.orbit_filename)

        @param.depends("orbits", "start_mjd", "end_mjd", watch=True)
        def update_positions(self):
            if self.orbits is None:
                print("No orbits, not updating positions")
                return

            print("Updating positions")
            self.positions = compute_minor_planet_positions(
                self.orbits, self.start_mjd, self.end_mjd, time_step=28
            )

        @param.depends("positions")
        def make_position_figure(self):
            if self.positions is None:
                return None

            figure = map_minor_planet_positions(self.positions)
            return figure

        @classmethod
        def make_app(cls):
            simple_dashboard = cls()
            simple_dashboard.update_orbits()

            app = pn.Row(
                pn.Param(
                    simple_dashboard, parameters=["orbit_filename", "start_mjd", "end_mjd"]
                ),
                pn.param.ParamMethod(
                    simple_dashboard.make_position_figure, loading_indicator=True
                ),
            )
            return app

Now we can use the app within our notebook:

.. code:: ipython3

    # Load the jupyter extension that allows the display of
    # panel dashboards within jupyter
    pn.extension()

    # Instantite the app
    app = SimpleSampleDashboard.make_app()

    # Actually display the app
    app







.. raw:: html

    <style>*[data-root-id],
    *[data-root-id] > * {
      box-sizing: border-box;
      font-family: var(--jp-ui-font-family);
      font-size: var(--jp-ui-font-size1);
      color: var(--vscode-editor-foreground, var(--jp-ui-font-color1));
    }

    /* Override VSCode background color */
    .cell-output-ipywidget-background:has(
        > .cell-output-ipywidget-background > .lm-Widget > *[data-root-id]
      ),
    .cell-output-ipywidget-background:has(> .lm-Widget > *[data-root-id]) {
      background-color: transparent !important;
    }
    </style>



.. raw:: html

    <div id='3f4252ae-7e67-460d-bd36-baa644be5ee1'>
      <div id="d8f1ada6-987c-495d-871a-82b9327cb377" data-root-id="3f4252ae-7e67-460d-bd36-baa644be5ee1" style="display: contents;"></div>
    </div>
    <script type="application/javascript">(function(root) {
      var docs_json = {"78bf17c8-31c3-4cc3-a229-c672d2d3d194":{"version":"3.2.1","title":"Bokeh Application","roots":[{"type":"object","name":"panel.models.browser.BrowserInfo","id":"3f4252ae-7e67-460d-bd36-baa644be5ee1"},{"type":"object","name":"panel.models.comm_manager.CommManager","id":"980af8b6-eea7-4f42-9c14-4f6a317f1637","attributes":{"plot_id":"3f4252ae-7e67-460d-bd36-baa644be5ee1","comm_id":"56679ab5f339472abdf8d41bcf606fc3","client_comm_id":"2e4ed2ca8b6a4af78f752841b1a05590"}}],"defs":[{"type":"model","name":"ReactiveHTML1"},{"type":"model","name":"FlexBox1","properties":[{"name":"align_content","kind":"Any","default":"flex-start"},{"name":"align_items","kind":"Any","default":"flex-start"},{"name":"flex_direction","kind":"Any","default":"row"},{"name":"flex_wrap","kind":"Any","default":"wrap"},{"name":"justify_content","kind":"Any","default":"flex-start"}]},{"type":"model","name":"FloatPanel1","properties":[{"name":"config","kind":"Any","default":{"type":"map"}},{"name":"contained","kind":"Any","default":true},{"name":"position","kind":"Any","default":"right-top"},{"name":"offsetx","kind":"Any","default":null},{"name":"offsety","kind":"Any","default":null},{"name":"theme","kind":"Any","default":"primary"},{"name":"status","kind":"Any","default":"normalized"}]},{"type":"model","name":"GridStack1","properties":[{"name":"mode","kind":"Any","default":"warn"},{"name":"ncols","kind":"Any","default":null},{"name":"nrows","kind":"Any","default":null},{"name":"allow_resize","kind":"Any","default":true},{"name":"allow_drag","kind":"Any","default":true},{"name":"state","kind":"Any","default":[]}]},{"type":"model","name":"drag1","properties":[{"name":"slider_width","kind":"Any","default":5},{"name":"slider_color","kind":"Any","default":"black"},{"name":"value","kind":"Any","default":50}]},{"type":"model","name":"click1","properties":[{"name":"terminal_output","kind":"Any","default":""},{"name":"debug_name","kind":"Any","default":""},{"name":"clears","kind":"Any","default":0}]},{"type":"model","name":"FastWrapper1","properties":[{"name":"object","kind":"Any","default":null},{"name":"style","kind":"Any","default":null}]},{"type":"model","name":"NotificationAreaBase1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0}]},{"type":"model","name":"NotificationArea1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"notifications","kind":"Any","default":[]},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0},{"name":"types","kind":"Any","default":[{"type":"map","entries":[["type","warning"],["background","#ffc107"],["icon",{"type":"map","entries":[["className","fas fa-exclamation-triangle"],["tagName","i"],["color","white"]]}]]},{"type":"map","entries":[["type","info"],["background","#007bff"],["icon",{"type":"map","entries":[["className","fas fa-info-circle"],["tagName","i"],["color","white"]]}]]}]}]},{"type":"model","name":"Notification","properties":[{"name":"background","kind":"Any","default":null},{"name":"duration","kind":"Any","default":3000},{"name":"icon","kind":"Any","default":null},{"name":"message","kind":"Any","default":""},{"name":"notification_type","kind":"Any","default":null},{"name":"_destroyed","kind":"Any","default":false}]},{"type":"model","name":"TemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"BootstrapTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"MaterialTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]}]}};
      var render_items = [{"docid":"78bf17c8-31c3-4cc3-a229-c672d2d3d194","roots":{"3f4252ae-7e67-460d-bd36-baa644be5ee1":"d8f1ada6-987c-495d-871a-82b9327cb377"},"root_ids":["3f4252ae-7e67-460d-bd36-baa644be5ee1"]}];
      var docs = Object.values(docs_json)
      if (!docs) {
        return
      }
      const py_version = docs[0].version.replace('rc', '-rc.').replace('.dev', '-dev.')
      const is_dev = py_version.indexOf("+") !== -1 || py_version.indexOf("-") !== -1
      function embed_document(root) {
        var Bokeh = get_bokeh(root)
        Bokeh.embed.embed_items_notebook(docs_json, render_items);
        for (const render_item of render_items) {
          for (const root_id of render_item.root_ids) {
    	const id_el = document.getElementById(root_id)
    	if (id_el.children.length && (id_el.children[0].className === 'bk-root')) {
    	  const root_el = id_el.children[0]
    	  root_el.id = root_el.id + '-rendered'
    	}
          }
        }
      }
      function get_bokeh(root) {
        if (root.Bokeh === undefined) {
          return null
        } else if (root.Bokeh.version !== py_version && !is_dev) {
          if (root.Bokeh.versions === undefined || !root.Bokeh.versions.has(py_version)) {
    	return null
          }
          return root.Bokeh.versions.get(py_version);
        } else if (root.Bokeh.version === py_version) {
          return root.Bokeh
        }
        return null
      }
      function is_loaded(root) {
        var Bokeh = get_bokeh(root)
        return (Bokeh != null && Bokeh.Panel !== undefined)
      }
      if (is_loaded(root)) {
        embed_document(root);
      } else {
        var attempts = 0;
        var timer = setInterval(function(root) {
          if (is_loaded(root)) {
            clearInterval(timer);
            embed_document(root);
          } else if (document.readyState == "complete") {
            attempts++;
            if (attempts > 200) {
              clearInterval(timer);
    	  var Bokeh = get_bokeh(root)
    	  if (Bokeh == null || Bokeh.Panel == null) {
                console.warn("Panel: ERROR: Unable to run Panel code because Bokeh or Panel library is missing");
    	  } else {
    	    console.warn("Panel: WARNING: Attempting to render but not all required libraries could be resolved.")
    	    embed_document(root)
    	  }
            }
          }
        }, 25, root)
      }
    })(window);</script>


.. parsed-literal::

    Updating orbits
    Updating positions






.. raw:: html

    <div id='4d44bc01-9859-49b6-b4a8-05fa88cf18f7'>
      <div id="e811a225-0c85-42bf-a580-b1256f3e6d59" data-root-id="4d44bc01-9859-49b6-b4a8-05fa88cf18f7" style="display: contents;"></div>
    </div>
    <script type="application/javascript">(function(root) {
      var docs_json = {"0f6ed190-4046-46f5-a146-5cdb8fe5d082":{"version":"3.2.1","title":"Bokeh Application","roots":[{"type":"object","name":"Row","id":"4d44bc01-9859-49b6-b4a8-05fa88cf18f7","attributes":{"name":"Row00156","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"type":"object","name":"ImportedStyleSheet","id":"5a271411-b26c-428a-86c2-31bd005e5f66","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/loading.css"}},{"type":"object","name":"ImportedStyleSheet","id":"81fd9bdc-cf09-49e8-9733-b9a6bc75759d","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/listpanel.css"}},{"type":"object","name":"ImportedStyleSheet","id":"27d0a998-7a64-4721-994b-58fe22ec92b3","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/bundled/theme/default.css"}},{"type":"object","name":"ImportedStyleSheet","id":"a17f441a-c9ac-4579-8969-0bc330b21356","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/bundled/theme/native.css"}}],"margin":0,"align":"start","children":[{"type":"object","name":"Column","id":"02fe50bc-8e8f-4ede-bf4f-89d41b30b2df","attributes":{"name":"SimpleSampleDashboard","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"id":"81fd9bdc-cf09-49e8-9733-b9a6bc75759d"},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"margin":[5,10],"align":"start","children":[{"type":"object","name":"Div","id":"11003704-4e2d-453e-9060-97b28d48f1d3","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"margin":[5,10],"align":"start","text":"<b>SimpleSampleDashboard</b>"}},{"type":"object","name":"panel.models.widgets.CustomSelect","id":"9a7e9813-a481-4ced-b06e-a7b01b3183e2","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"type":"object","name":"ImportedStyleSheet","id":"41216a13-74cd-45e4-a651-6abc5eabd8b7","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/select.css"}},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"Orbit data file","description":{"type":"object","name":"Tooltip","id":"ca88c503-894d-48ed-8c03-8405f833d01c","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"b2491740-da06-41da-a4e7-fb2191f93105","attributes":{"html":"<p>Data file with orbit parameters</p>\n"}}}},"options":[["./mpcorb_sample_big.dat","mpcorb_sample_big.dat"],["./mpcorb_sample_sdss.dat","mpcorb_sample_sdss.dat"]],"value":"./mpcorb_sample_big.dat"}},{"type":"object","name":"Spinner","id":"9954e4af-8988-44b0-87dd-69752a3fb3b9","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"Start MJD","description":{"type":"object","name":"Tooltip","id":"b6f3b692-ce1f-4e05-a1b3-ad12a2a74648","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"4c3a6d8f-9ef0-4f92-93ec-6b4c4a53f2ba","attributes":{"html":"<p>Modified Julian Date of start of date window</p>\n"}}}},"value":60200,"step":0.1}},{"type":"object","name":"Spinner","id":"119b707a-c827-4496-9e70-01a2f26ebb8d","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"End MJD","description":{"type":"object","name":"Tooltip","id":"0d6d131f-86d7-4967-92a4-3ac1d17fc062","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"60077c1f-8675-4061-985b-7298cd0b2615","attributes":{"html":"<p>Modified Julian Date of end of date window</p>\n"}}}},"value":60565,"step":0.1}}]}},{"type":"object","name":"Column","id":"9aa23d40-a361-49db-b46a-9057bde6c4aa","attributes":{"name":"Column00147","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"5a271411-b26c-428a-86c2-31bd005e5f66"},{"id":"81fd9bdc-cf09-49e8-9733-b9a6bc75759d"},{"id":"27d0a998-7a64-4721-994b-58fe22ec92b3"},{"id":"a17f441a-c9ac-4579-8969-0bc330b21356"}],"margin":0,"align":"start","children":[{"type":"object","name":"Figure","id":"51f63c66-3719-479a-99fc-4b9be856ac0b","attributes":{"x_range":{"type":"object","name":"DataRange1d","id":"ccdcc47e-36c9-4d82-a299-87c0564f02e5"},"y_range":{"type":"object","name":"DataRange1d","id":"aa59ded4-64ad-4a19-9118-9b293782a68d"},"x_scale":{"type":"object","name":"LinearScale","id":"35787ed3-325c-4662-95cb-640ee8a7807d"},"y_scale":{"type":"object","name":"LinearScale","id":"4b1f94e8-b130-4ea4-bcfc-c1ea630023d5"},"title":{"type":"object","name":"Title","id":"f8d663ff-e176-416f-96a9-ef928ecee74f","attributes":{"text":"Select minor planet positions"}},"renderers":[{"type":"object","name":"GlyphRenderer","id":"f49131ae-f868-404d-a97e-5b0474ef6223","attributes":{"data_source":{"type":"object","name":"ColumnDataSource","id":"349f580b-9ee7-4d60-8943-69ff9eff6003","attributes":{"selected":{"type":"object","name":"Selection","id":"e4d005b1-4095-466f-b82a-b00ed4ef45a6","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"c15d57cc-c293-4f20-8d7f-22e1a4580191"},"data":{"type":"map","entries":[["designation",["(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta"]],["mjd",[60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905]],["ra",[208.46090632821364,220.2116056863774,232.8204917316707,245.94333371548575,259.06078216013736,271.4402424999108,282.1455223684826,289.9952153675278,293.46445820177547,291.152513740418,284.3665202377227,278.91471527934533,279.1863995622094,181.47176383086338,195.4877606416074,209.19878677635734,222.3746233367172,234.45113142600323,244.43949915871264,250.908959188178,252.25842032776185,248.13772348363497,241.8669260882815,238.51643723296465,239.9405475527263,245.30233300209005,134.18841950981565,147.58358371669956,158.69548999827074,166.67919216631532,170.07963407990772,167.6904719925837,161.76605848244716,158.1885172886842,159.72660497236487,165.25699763246166,173.12286195400367,182.2595718980277,192.09132138649292,89.37770584979619,96.04934360081415,97.20511604139986,91.62315329202856,83.615460201681,80.73641402769873,84.78633607125536,93.77086777522194,105.68226001494749,119.12906709204258,133.19648901237895,147.33935992821637,161.29958836924848]],["decl",[-6.15126163916317,-11.315262502975761,-15.73743455805142,-19.153109324103315,-21.430951183506153,-22.658726683592516,-23.202226651650136,-23.705373019939948,-24.959204661849764,-27.333998632750014,-29.788518952457153,-30.880464028976558,-30.816158293013576,4.992159798722879,2.6399645580800692,0.9068137038068282,0.46886088336992277,1.9475143986119872,5.794720046787787,12.010489260376833,19.49311338650011,25.37562376821884,26.61778769378039,23.356753406818513,18.017699831607704,12.55304781382618,9.2694185580391,5.358870413149805,1.5918467410678245,-1.1209319355867615,-1.6387801757588207,1.0581901528008741,5.973992514786412,9.716711350342713,10.708890719675546,9.518557888556128,6.962477980350667,3.646519599117515,0.03195970654525,19.069567139412932,19.002217340406517,19.208789016473418,20.180351345778494,21.48433166089078,22.761119255353094,23.99181070324241,24.77292483155828,24.61604397690494,23.22610874948374,20.550031291150034,16.7398611993294,12.095577036042929]],["distance",[3.3738815451112156,3.592845331822669,3.7035607598265043,3.69253704465821,3.556462739573592,3.305192223211393,2.9637789376010875,2.57474216085964,2.203486822451228,1.9445244549949297,1.89930975102985,2.096260407517126,2.459978978463117,3.3473828529090612,3.4093147726379156,3.360399022117786,3.206398915653871,2.967753019683161,2.681874567879268,2.4044467718062013,2.2065319815776157,2.156461916104825,2.282268390748213,2.553303471074915,2.9082948005490787,3.2872337455241585,2.9389033196883054,2.7637655925062123,2.5121252890576757,2.205539785793172,1.899828288813873,1.6990761638748033,1.7245422724829065,2.0005970220164966,2.4330349823339983,2.915044317591086,3.371879942038738,3.75325216232905,4.023163808490896,2.541292227149632,2.1469119642998415,1.7942335405726815,1.5952242201345324,1.6472266787328194,1.9193684046827897,2.2925467520890512,2.669238286307661,2.993342709072747,3.235375861393669,3.3807296756772085,3.4232787704175536,3.3623327562812113]]]}}},"view":{"type":"object","name":"CDSView","id":"2d1500af-2ed5-4bd2-8c05-e576830432ea","attributes":{"filter":{"type":"object","name":"AllIndices","id":"18af21b2-f4c9-4446-a029-7deb677fb490"}}},"glyph":{"type":"object","name":"Scatter","id":"0e090361-e4b7-44de-a24d-ac9c1070165a","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"type":"object","name":"CategoricalColorMapper","id":"63e72745-dffa-41fc-89e9-328d418d4c22","attributes":{"palette":["#1f77b4","#aec7e8","#ff7f0e","#ffbb78"],"factors":{"type":"ndarray","array":["(1) Ceres","(2) Pallas","(3) Juno","(4) Vesta"],"shape":[4],"dtype":"object","order":"little"}}}},"fill_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"hatch_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}}}},"nonselection_glyph":{"type":"object","name":"Scatter","id":"9f636dad-b60b-4310-b475-099b3cc43b67","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"line_alpha":{"type":"value","value":0.1},"fill_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"fill_alpha":{"type":"value","value":0.1},"hatch_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"hatch_alpha":{"type":"value","value":0.1}}},"muted_glyph":{"type":"object","name":"Scatter","id":"19d98522-3860-4bf6-b506-912930cc4415","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"line_alpha":{"type":"value","value":0.2},"fill_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"fill_alpha":{"type":"value","value":0.2},"hatch_color":{"type":"field","field":"designation","transform":{"id":"63e72745-dffa-41fc-89e9-328d418d4c22"}},"hatch_alpha":{"type":"value","value":0.2}}}}}],"toolbar":{"type":"object","name":"Toolbar","id":"6047f485-3d54-48a9-b3e4-6e2608b6e973","attributes":{"tools":[{"type":"object","name":"PanTool","id":"ad7ee99a-8b4e-4a2a-98b3-0dc317bed299"},{"type":"object","name":"WheelZoomTool","id":"b6fabab5-660d-4cfa-99f6-4db45cb5434f"},{"type":"object","name":"BoxZoomTool","id":"3ee89d99-1257-4bf4-af89-6c9cd011a49a","attributes":{"overlay":{"type":"object","name":"BoxAnnotation","id":"2a7a030c-7695-433d-af17-602dbfcc3fe7","attributes":{"syncable":false,"level":"overlay","visible":false,"left_units":"canvas","right_units":"canvas","bottom_units":"canvas","top_units":"canvas","line_color":"black","line_alpha":1.0,"line_width":2,"line_dash":[4,4],"fill_color":"lightgrey","fill_alpha":0.5}}}},{"type":"object","name":"SaveTool","id":"35c86e66-4280-458e-bc35-a79b5e16344a"},{"type":"object","name":"ResetTool","id":"bdd5c245-c535-44d3-8956-3a683e035888"},{"type":"object","name":"HelpTool","id":"d1c68ec8-ba1b-4cb5-b5cc-cd34d74ee037"}]}},"left":[{"type":"object","name":"LinearAxis","id":"f18347fd-a6fc-4c77-a899-c647f31bc140","attributes":{"ticker":{"type":"object","name":"BasicTicker","id":"0d12d43d-deea-40a8-aca7-bdf55ce0b589","attributes":{"mantissas":[1,2,5]}},"formatter":{"type":"object","name":"BasicTickFormatter","id":"1d90d35c-8e01-43f5-9cbf-1110f25975d0"},"axis_label":"Declination (degrees)","major_label_policy":{"type":"object","name":"AllLabels","id":"13a7fe34-ff65-4b68-ad7a-916181a94a1b"}}}],"below":[{"type":"object","name":"LinearAxis","id":"064fda95-e3e3-4b26-8ad8-fb3685ff996e","attributes":{"ticker":{"type":"object","name":"BasicTicker","id":"1c5ecd78-e8b9-471c-8fea-2e48cd148cb5","attributes":{"mantissas":[1,2,5]}},"formatter":{"type":"object","name":"BasicTickFormatter","id":"6fc56086-863d-45af-bb92-0989435b8e07"},"axis_label":"R.A. (degrees)","major_label_policy":{"type":"object","name":"AllLabels","id":"7c62e0ac-0ef3-428f-9505-0719bd10b34e"}}}],"center":[{"type":"object","name":"Grid","id":"32e95250-6d12-476e-b279-85db847c3fba","attributes":{"axis":{"id":"064fda95-e3e3-4b26-8ad8-fb3685ff996e"}}},{"type":"object","name":"Grid","id":"557ddf61-39b0-4579-b335-e873b20c8719","attributes":{"dimension":1,"axis":{"id":"f18347fd-a6fc-4c77-a899-c647f31bc140"}}},{"type":"object","name":"Legend","id":"689faf2b-a3a5-4141-ab78-eff48d5ac2c0","attributes":{"items":[{"type":"object","name":"LegendItem","id":"f55a2c03-6af8-47c8-9be0-2d00c8386950","attributes":{"label":{"type":"field","field":"designation"},"renderers":[{"id":"f49131ae-f868-404d-a97e-5b0474ef6223"}]}}]}}]}}]}}]}},{"type":"object","name":"panel.models.comm_manager.CommManager","id":"fbf8d355-8360-45f0-b91d-09e84dcfef8a","attributes":{"plot_id":"4d44bc01-9859-49b6-b4a8-05fa88cf18f7","comm_id":"8d08558e26ba421081c04772a19ddfd5","client_comm_id":"58e6f5dc23b14436870f6421528a8af4"}}],"defs":[{"type":"model","name":"ReactiveHTML1"},{"type":"model","name":"FlexBox1","properties":[{"name":"align_content","kind":"Any","default":"flex-start"},{"name":"align_items","kind":"Any","default":"flex-start"},{"name":"flex_direction","kind":"Any","default":"row"},{"name":"flex_wrap","kind":"Any","default":"wrap"},{"name":"justify_content","kind":"Any","default":"flex-start"}]},{"type":"model","name":"FloatPanel1","properties":[{"name":"config","kind":"Any","default":{"type":"map"}},{"name":"contained","kind":"Any","default":true},{"name":"position","kind":"Any","default":"right-top"},{"name":"offsetx","kind":"Any","default":null},{"name":"offsety","kind":"Any","default":null},{"name":"theme","kind":"Any","default":"primary"},{"name":"status","kind":"Any","default":"normalized"}]},{"type":"model","name":"GridStack1","properties":[{"name":"mode","kind":"Any","default":"warn"},{"name":"ncols","kind":"Any","default":null},{"name":"nrows","kind":"Any","default":null},{"name":"allow_resize","kind":"Any","default":true},{"name":"allow_drag","kind":"Any","default":true},{"name":"state","kind":"Any","default":[]}]},{"type":"model","name":"drag1","properties":[{"name":"slider_width","kind":"Any","default":5},{"name":"slider_color","kind":"Any","default":"black"},{"name":"value","kind":"Any","default":50}]},{"type":"model","name":"click1","properties":[{"name":"terminal_output","kind":"Any","default":""},{"name":"debug_name","kind":"Any","default":""},{"name":"clears","kind":"Any","default":0}]},{"type":"model","name":"FastWrapper1","properties":[{"name":"object","kind":"Any","default":null},{"name":"style","kind":"Any","default":null}]},{"type":"model","name":"NotificationAreaBase1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0}]},{"type":"model","name":"NotificationArea1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"notifications","kind":"Any","default":[]},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0},{"name":"types","kind":"Any","default":[{"type":"map","entries":[["type","warning"],["background","#ffc107"],["icon",{"type":"map","entries":[["className","fas fa-exclamation-triangle"],["tagName","i"],["color","white"]]}]]},{"type":"map","entries":[["type","info"],["background","#007bff"],["icon",{"type":"map","entries":[["className","fas fa-info-circle"],["tagName","i"],["color","white"]]}]]}]}]},{"type":"model","name":"Notification","properties":[{"name":"background","kind":"Any","default":null},{"name":"duration","kind":"Any","default":3000},{"name":"icon","kind":"Any","default":null},{"name":"message","kind":"Any","default":""},{"name":"notification_type","kind":"Any","default":null},{"name":"_destroyed","kind":"Any","default":false}]},{"type":"model","name":"TemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"BootstrapTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"MaterialTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]}]}};
      var render_items = [{"docid":"0f6ed190-4046-46f5-a146-5cdb8fe5d082","roots":{"4d44bc01-9859-49b6-b4a8-05fa88cf18f7":"e811a225-0c85-42bf-a580-b1256f3e6d59"},"root_ids":["4d44bc01-9859-49b6-b4a8-05fa88cf18f7"]}];
      var docs = Object.values(docs_json)
      if (!docs) {
        return
      }
      const py_version = docs[0].version.replace('rc', '-rc.').replace('.dev', '-dev.')
      const is_dev = py_version.indexOf("+") !== -1 || py_version.indexOf("-") !== -1
      function embed_document(root) {
        var Bokeh = get_bokeh(root)
        Bokeh.embed.embed_items_notebook(docs_json, render_items);
        for (const render_item of render_items) {
          for (const root_id of render_item.root_ids) {
    	const id_el = document.getElementById(root_id)
    	if (id_el.children.length && (id_el.children[0].className === 'bk-root')) {
    	  const root_el = id_el.children[0]
    	  root_el.id = root_el.id + '-rendered'
    	}
          }
        }
      }
      function get_bokeh(root) {
        if (root.Bokeh === undefined) {
          return null
        } else if (root.Bokeh.version !== py_version && !is_dev) {
          if (root.Bokeh.versions === undefined || !root.Bokeh.versions.has(py_version)) {
    	return null
          }
          return root.Bokeh.versions.get(py_version);
        } else if (root.Bokeh.version === py_version) {
          return root.Bokeh
        }
        return null
      }
      function is_loaded(root) {
        var Bokeh = get_bokeh(root)
        return (Bokeh != null && Bokeh.Panel !== undefined)
      }
      if (is_loaded(root)) {
        embed_document(root);
      } else {
        var attempts = 0;
        var timer = setInterval(function(root) {
          if (is_loaded(root)) {
            clearInterval(timer);
            embed_document(root);
          } else if (document.readyState == "complete") {
            attempts++;
            if (attempts > 200) {
              clearInterval(timer);
    	  var Bokeh = get_bokeh(root)
    	  if (Bokeh == null || Bokeh.Panel == null) {
                console.warn("Panel: ERROR: Unable to run Panel code because Bokeh or Panel library is missing");
    	  } else {
    	    console.warn("Panel: WARNING: Attempting to render but not all required libraries could be resolved.")
    	    embed_document(root)
    	  }
            }
          }
        }, 25, root)
      }
    })(window);</script>



Making a stand-alone app
------------------------

To create a stand-alone app that can be run as its own web service,
outside ``jupyter``, a driver function needs to be added.

For the above example, it would look something like this:

.. code:: ipython3

    def main():
        # In this trivial example, this extra declaration
        # is pointless functionally. But, in a real app,
        # you probably want to use something like this
        # to make sure relevant configuration arguments
        # get passed.
        def make_app():
            return SimpleSampleDashboard.make_app()

        pn.serve(make_app, port=8080, title="Simple Sample Dashboard")

Then, an entry point for the new dashboard can be added to
``pyproject.toml`` so that an executable to start the server is added to
the path when the python module is installed.
