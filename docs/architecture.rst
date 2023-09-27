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
stage at a time, using an example chosen to demonstrate the principles
underlying the chosen architecture.

In this example, we build a dashboard that shows the locations of minor
planets (in equatorial coordinates) over a period of time. This
application is outside the scope of the content intended to included in
``schedview``, which only packages scheduler and progress related
visualizations. ``schedview``\ ’s basic architecture, however, is
applicable beyond its scope. This example was chosen because it is an
application to real-world data that is complex enough to demonstrate all
aspects of the architecture, and can be implemented in this architecture
with a minimum of additional application-specific complexities that
would distract from them.

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
``skyfield``. On the other hand, it did include the data restructuring
needed to apply the data in the format returned by the function in the
collection step to ``skyfield``, and transform the results into python
objects well suited to being passed directly to the plotting tools being
used.

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
            <span id="d13cd303-d610-40a8-aeda-fd3944066ca3">Loading BokehJS ...</span>
        </div>






.. raw:: html


    <div id="b2eb12ad-c462-45cf-a046-3450288586ab" data-root-id="p1004" style="display: contents;"></div>





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

    <div id='e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e'>
      <div id="def0e575-d6fc-4b83-8307-2adfc5da82c6" data-root-id="e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e" style="display: contents;"></div>
    </div>
    <script type="application/javascript">(function(root) {
      var docs_json = {"db2fcb6b-b6d2-43b2-ae84-f14c9fcc9d40":{"version":"3.2.1","title":"Bokeh Application","roots":[{"type":"object","name":"panel.models.browser.BrowserInfo","id":"e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e"},{"type":"object","name":"panel.models.comm_manager.CommManager","id":"06613153-67b1-495c-a983-aaf1eb3a91d8","attributes":{"plot_id":"e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e","comm_id":"75be809ec39849399a8a1408c2d1070f","client_comm_id":"aacfecc56abc4895a219c3bfecfa939b"}}],"defs":[{"type":"model","name":"ReactiveHTML1"},{"type":"model","name":"FlexBox1","properties":[{"name":"align_content","kind":"Any","default":"flex-start"},{"name":"align_items","kind":"Any","default":"flex-start"},{"name":"flex_direction","kind":"Any","default":"row"},{"name":"flex_wrap","kind":"Any","default":"wrap"},{"name":"justify_content","kind":"Any","default":"flex-start"}]},{"type":"model","name":"FloatPanel1","properties":[{"name":"config","kind":"Any","default":{"type":"map"}},{"name":"contained","kind":"Any","default":true},{"name":"position","kind":"Any","default":"right-top"},{"name":"offsetx","kind":"Any","default":null},{"name":"offsety","kind":"Any","default":null},{"name":"theme","kind":"Any","default":"primary"},{"name":"status","kind":"Any","default":"normalized"}]},{"type":"model","name":"GridStack1","properties":[{"name":"mode","kind":"Any","default":"warn"},{"name":"ncols","kind":"Any","default":null},{"name":"nrows","kind":"Any","default":null},{"name":"allow_resize","kind":"Any","default":true},{"name":"allow_drag","kind":"Any","default":true},{"name":"state","kind":"Any","default":[]}]},{"type":"model","name":"drag1","properties":[{"name":"slider_width","kind":"Any","default":5},{"name":"slider_color","kind":"Any","default":"black"},{"name":"value","kind":"Any","default":50}]},{"type":"model","name":"click1","properties":[{"name":"terminal_output","kind":"Any","default":""},{"name":"debug_name","kind":"Any","default":""},{"name":"clears","kind":"Any","default":0}]},{"type":"model","name":"FastWrapper1","properties":[{"name":"object","kind":"Any","default":null},{"name":"style","kind":"Any","default":null}]},{"type":"model","name":"NotificationAreaBase1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0}]},{"type":"model","name":"NotificationArea1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"notifications","kind":"Any","default":[]},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0},{"name":"types","kind":"Any","default":[{"type":"map","entries":[["type","warning"],["background","#ffc107"],["icon",{"type":"map","entries":[["className","fas fa-exclamation-triangle"],["tagName","i"],["color","white"]]}]]},{"type":"map","entries":[["type","info"],["background","#007bff"],["icon",{"type":"map","entries":[["className","fas fa-info-circle"],["tagName","i"],["color","white"]]}]]}]}]},{"type":"model","name":"Notification","properties":[{"name":"background","kind":"Any","default":null},{"name":"duration","kind":"Any","default":3000},{"name":"icon","kind":"Any","default":null},{"name":"message","kind":"Any","default":""},{"name":"notification_type","kind":"Any","default":null},{"name":"_destroyed","kind":"Any","default":false}]},{"type":"model","name":"TemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"BootstrapTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"MaterialTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]}]}};
      var render_items = [{"docid":"db2fcb6b-b6d2-43b2-ae84-f14c9fcc9d40","roots":{"e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e":"def0e575-d6fc-4b83-8307-2adfc5da82c6"},"root_ids":["e05ef6ea-4dd8-4ba9-a6a8-f31e2ee34e1e"]}];
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

    <div id='ff448e6d-6846-46c4-b3af-6359c2945424'>
      <div id="a162233f-57ea-4f32-83d3-1b1d49e8c764" data-root-id="ff448e6d-6846-46c4-b3af-6359c2945424" style="display: contents;"></div>
    </div>
    <script type="application/javascript">(function(root) {
      var docs_json = {"362dc27d-4ba0-4644-a785-222a07aa0b97":{"version":"3.2.1","title":"Bokeh Application","roots":[{"type":"object","name":"Row","id":"ff448e6d-6846-46c4-b3af-6359c2945424","attributes":{"name":"Row00156","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"type":"object","name":"ImportedStyleSheet","id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/loading.css"}},{"type":"object","name":"ImportedStyleSheet","id":"e63af4dd-ede9-4ea1-9dcf-513b829ff5af","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/listpanel.css"}},{"type":"object","name":"ImportedStyleSheet","id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/bundled/theme/default.css"}},{"type":"object","name":"ImportedStyleSheet","id":"fab7f0f2-4288-4f58-899e-29499e63c042","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/bundled/theme/native.css"}}],"margin":0,"align":"start","children":[{"type":"object","name":"Column","id":"4b7cea21-5f04-4bca-ac64-17df7744e20e","attributes":{"name":"SimpleSampleDashboard","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"id":"e63af4dd-ede9-4ea1-9dcf-513b829ff5af"},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"margin":[5,10],"align":"start","children":[{"type":"object","name":"Div","id":"07a4682a-c265-435f-a16f-e7a15dadd604","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"margin":[5,10],"align":"start","text":"<b>SimpleSampleDashboard</b>"}},{"type":"object","name":"panel.models.widgets.CustomSelect","id":"97ba2c1a-0651-40fb-87d6-df052c0c47e4","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"type":"object","name":"ImportedStyleSheet","id":"7a9b3a7b-95b7-41dc-98bb-c15afe16c060","attributes":{"url":"https://cdn.holoviz.org/panel/1.2.1/dist/css/select.css"}},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"Orbit data file","description":{"type":"object","name":"Tooltip","id":"0ce65b94-05da-4e2f-bd97-754df6f3405c","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"e3225d5e-a1f3-446f-81a9-5832f63d640b","attributes":{"html":"<p>Data file with orbit parameters</p>\n"}}}},"options":[["./mpcorb_sample_big.dat","mpcorb_sample_big.dat"],["./mpcorb_sample_sdss.dat","mpcorb_sample_sdss.dat"]],"value":"./mpcorb_sample_big.dat"}},{"type":"object","name":"Spinner","id":"9d1d6219-1dbd-4796-ac70-0dd3e7c1e49d","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"Start MJD","description":{"type":"object","name":"Tooltip","id":"21480a9d-5fc0-43ca-a03f-b523f7bb63a9","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"c6d3d23e-db62-4968-97ed-6d8f70c975ee","attributes":{"html":"<p>Modified Julian Date of start of date window</p>\n"}}}},"value":60200,"step":0.1}},{"type":"object","name":"Spinner","id":"ea83714a-e49a-4183-8d3a-6b032b8176a7","attributes":{"stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"width":300,"min_width":300,"margin":[5,10],"align":"start","title":"End MJD","description":{"type":"object","name":"Tooltip","id":"b24f4163-6734-4c9b-800e-0913ee2a1704","attributes":{"syncable":false,"stylesheets":[":host { white-space: initial; max-width: 300px; }"],"position":"right","content":{"type":"object","name":"bokeh.models.dom.HTML","id":"5f44a563-a82b-4078-8574-aa271b371b05","attributes":{"html":"<p>Modified Julian Date of end of date window</p>\n"}}}},"value":60565,"step":0.1}}]}},{"type":"object","name":"Column","id":"53c8712a-6623-4c53-89cc-24434c526dc8","attributes":{"name":"Column00147","stylesheets":["\n:host(.pn-loading.pn-arc):before, .pn-loading.pn-arc:before {\n  background-image: url(\"data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHN0eWxlPSJtYXJnaW46IGF1dG87IGJhY2tncm91bmQ6IG5vbmU7IGRpc3BsYXk6IGJsb2NrOyBzaGFwZS1yZW5kZXJpbmc6IGF1dG87IiB2aWV3Qm94PSIwIDAgMTAwIDEwMCIgcHJlc2VydmVBc3BlY3RSYXRpbz0ieE1pZFlNaWQiPiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYzNjM2MzIiBzdHJva2Utd2lkdGg9IjEwIiByPSIzNSIgc3Ryb2tlLWRhc2hhcnJheT0iMTY0LjkzMzYxNDMxMzQ2NDE1IDU2Ljk3Nzg3MTQzNzgyMTM4Ij4gICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJyb3RhdGUiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIiBkdXI9IjFzIiB2YWx1ZXM9IjAgNTAgNTA7MzYwIDUwIDUwIiBrZXlUaW1lcz0iMDsxIj48L2FuaW1hdGVUcmFuc2Zvcm0+ICA8L2NpcmNsZT48L3N2Zz4=\");\n  background-size: auto calc(min(50%, 400px));\n}",{"id":"ebfd78c6-8dfd-4f81-819f-5f7079b99d3b"},{"id":"e63af4dd-ede9-4ea1-9dcf-513b829ff5af"},{"id":"e2fb78e3-653c-4f86-a69e-2db74e7467ee"},{"id":"fab7f0f2-4288-4f58-899e-29499e63c042"}],"margin":0,"align":"start","children":[{"type":"object","name":"Figure","id":"1f84790f-05a6-4255-ab84-a7eecc43baf9","attributes":{"x_range":{"type":"object","name":"DataRange1d","id":"b2e0ac8e-34a0-4de1-b575-f82723adc01e"},"y_range":{"type":"object","name":"DataRange1d","id":"d8bc375f-b198-47c3-b49b-5ea0d8c5d320"},"x_scale":{"type":"object","name":"LinearScale","id":"76ae10b1-960e-4753-abbb-4c86898d202e"},"y_scale":{"type":"object","name":"LinearScale","id":"39dbfc9a-901a-4c59-89b1-785a77d4015a"},"title":{"type":"object","name":"Title","id":"eff31b69-6268-49e2-8035-5a5b8b03c073","attributes":{"text":"Select minor planet positions"}},"renderers":[{"type":"object","name":"GlyphRenderer","id":"48b2580d-d01a-4b54-a532-31c51da77036","attributes":{"data_source":{"type":"object","name":"ColumnDataSource","id":"c519738d-a605-486b-8a52-06a37a6493bd","attributes":{"selected":{"type":"object","name":"Selection","id":"5581ccb1-b190-48b7-b485-345464e15bd4","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"c86ce789-87ab-475b-83c0-83bd2fec9343"},"data":{"type":"map","entries":[["designation",["(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(1) Ceres","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(2) Pallas","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(3) Juno","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta","(4) Vesta"]],["mjd",[60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905,60200.000800740905,60230.41746740742,60260.834134074394,60291.250800740905,60321.66746740742,60352.084134074394,60382.500800740905,60412.91746740742,60443.334134074394,60473.750800740905,60504.16746740742,60534.584134074394,60565.000800740905]],["ra",[208.46090632821364,220.2116056863774,232.8204917316707,245.94333371548575,259.06078216013736,271.4402424999108,282.1455223684826,289.9952153675278,293.46445820177547,291.152513740418,284.3665202377227,278.91471527934533,279.1863995622094,181.47176383086338,195.4877606416074,209.19878677635734,222.3746233367172,234.45113142600323,244.43949915871264,250.908959188178,252.25842032776185,248.13772348363497,241.8669260882815,238.51643723296465,239.9405475527263,245.30233300209005,134.18841950981565,147.58358371669956,158.69548999827074,166.67919216631532,170.07963407990772,167.6904719925837,161.76605848244716,158.1885172886842,159.72660497236487,165.25699763246166,173.12286195400367,182.2595718980277,192.09132138649292,89.37770584979619,96.04934360081415,97.20511604139986,91.62315329202856,83.615460201681,80.73641402769873,84.78633607125536,93.77086777522194,105.68226001494749,119.12906709204258,133.19648901237895,147.33935992821637,161.29958836924848]],["decl",[-6.15126163916317,-11.315262502975761,-15.73743455805142,-19.153109324103315,-21.430951183506153,-22.658726683592516,-23.202226651650136,-23.705373019939948,-24.959204661849764,-27.333998632750014,-29.788518952457153,-30.880464028976558,-30.816158293013576,4.992159798722879,2.6399645580800692,0.9068137038068282,0.46886088336992277,1.9475143986119872,5.794720046787787,12.010489260376833,19.49311338650011,25.37562376821884,26.61778769378039,23.356753406818513,18.017699831607704,12.55304781382618,9.2694185580391,5.358870413149805,1.5918467410678245,-1.1209319355867615,-1.6387801757588207,1.0581901528008741,5.973992514786412,9.716711350342713,10.708890719675546,9.518557888556128,6.962477980350667,3.646519599117515,0.03195970654525,19.069567139412932,19.002217340406517,19.208789016473418,20.180351345778494,21.48433166089078,22.761119255353094,23.99181070324241,24.77292483155828,24.61604397690494,23.22610874948374,20.550031291150034,16.7398611993294,12.095577036042929]],["distance",[3.3738815451112156,3.592845331822669,3.7035607598265043,3.69253704465821,3.556462739573592,3.305192223211393,2.9637789376010875,2.57474216085964,2.203486822451228,1.9445244549949297,1.89930975102985,2.096260407517126,2.459978978463117,3.3473828529090612,3.4093147726379156,3.360399022117786,3.206398915653871,2.967753019683161,2.681874567879268,2.4044467718062013,2.2065319815776157,2.156461916104825,2.282268390748213,2.553303471074915,2.9082948005490787,3.2872337455241585,2.9389033196883054,2.7637655925062123,2.5121252890576757,2.205539785793172,1.899828288813873,1.6990761638748033,1.7245422724829065,2.0005970220164966,2.4330349823339983,2.915044317591086,3.371879942038738,3.75325216232905,4.023163808490896,2.541292227149632,2.1469119642998415,1.7942335405726815,1.5952242201345324,1.6472266787328194,1.9193684046827897,2.2925467520890512,2.669238286307661,2.993342709072747,3.235375861393669,3.3807296756772085,3.4232787704175536,3.3623327562812113]]]}}},"view":{"type":"object","name":"CDSView","id":"3f92bb46-3975-48ad-ac08-53551151896f","attributes":{"filter":{"type":"object","name":"AllIndices","id":"afb20185-535d-4e32-be8e-1b57adcd5988"}}},"glyph":{"type":"object","name":"Scatter","id":"0ee144cc-72e3-4c1a-be60-6a0ab0ea7c01","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"type":"object","name":"CategoricalColorMapper","id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9","attributes":{"palette":["#1f77b4","#aec7e8","#ff7f0e","#ffbb78"],"factors":{"type":"ndarray","array":["(1) Ceres","(2) Pallas","(3) Juno","(4) Vesta"],"shape":[4],"dtype":"object","order":"little"}}}},"fill_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"hatch_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}}}},"nonselection_glyph":{"type":"object","name":"Scatter","id":"c9de083c-b87d-442c-832f-84b63868d1b9","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"line_alpha":{"type":"value","value":0.1},"fill_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"fill_alpha":{"type":"value","value":0.1},"hatch_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"hatch_alpha":{"type":"value","value":0.1}}},"muted_glyph":{"type":"object","name":"Scatter","id":"8aad964f-fd18-4bd8-89f2-753db12f489a","attributes":{"x":{"type":"field","field":"ra"},"y":{"type":"field","field":"decl"},"line_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"line_alpha":{"type":"value","value":0.2},"fill_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"fill_alpha":{"type":"value","value":0.2},"hatch_color":{"type":"field","field":"designation","transform":{"id":"3d495ac6-d819-4c82-b8f9-6509a34d89e9"}},"hatch_alpha":{"type":"value","value":0.2}}}}}],"toolbar":{"type":"object","name":"Toolbar","id":"97587534-9d0f-4b12-9532-e161d90c506d","attributes":{"tools":[{"type":"object","name":"PanTool","id":"7d6577d1-66ed-43cc-9001-ecc2c5c894b8"},{"type":"object","name":"WheelZoomTool","id":"ed9cd87c-801a-468b-a151-4eba2be632b5"},{"type":"object","name":"BoxZoomTool","id":"fe5b671c-8db8-4e4b-ab96-f1f409bd1506","attributes":{"overlay":{"type":"object","name":"BoxAnnotation","id":"2df2ac63-2441-448d-9aca-6b3b0d89ca5d","attributes":{"syncable":false,"level":"overlay","visible":false,"left_units":"canvas","right_units":"canvas","bottom_units":"canvas","top_units":"canvas","line_color":"black","line_alpha":1.0,"line_width":2,"line_dash":[4,4],"fill_color":"lightgrey","fill_alpha":0.5}}}},{"type":"object","name":"SaveTool","id":"390159b5-f6aa-4872-93dd-45bb05e7c1d3"},{"type":"object","name":"ResetTool","id":"3b1c8268-cc90-4267-af5c-bffc0b966730"},{"type":"object","name":"HelpTool","id":"6951c4f3-8c42-4071-9aa8-a37cb8a592a4"}]}},"left":[{"type":"object","name":"LinearAxis","id":"0f0cca9d-1cfe-4918-b27f-b72a72f4d151","attributes":{"ticker":{"type":"object","name":"BasicTicker","id":"3dbaa3f5-e678-44e2-bfea-e72175e60371","attributes":{"mantissas":[1,2,5]}},"formatter":{"type":"object","name":"BasicTickFormatter","id":"e3bbc6ca-abbc-46df-a1f0-8dcc70228c83"},"axis_label":"Declination (degrees)","major_label_policy":{"type":"object","name":"AllLabels","id":"ef8ce7d8-738f-49e7-94c4-07e936e06a54"}}}],"below":[{"type":"object","name":"LinearAxis","id":"ed317848-fc40-496f-bc44-0d90272604d9","attributes":{"ticker":{"type":"object","name":"BasicTicker","id":"dd0e96c4-6ff4-4c99-b5d8-29207d1e409a","attributes":{"mantissas":[1,2,5]}},"formatter":{"type":"object","name":"BasicTickFormatter","id":"dd349f13-6300-44ca-ae66-276fd7d37459"},"axis_label":"R.A. (degrees)","major_label_policy":{"type":"object","name":"AllLabels","id":"877a61f5-9f16-41a3-b58b-fc8dd5b46fed"}}}],"center":[{"type":"object","name":"Grid","id":"0915c559-529f-4aa1-a60c-9fd43f06c75d","attributes":{"axis":{"id":"ed317848-fc40-496f-bc44-0d90272604d9"}}},{"type":"object","name":"Grid","id":"242fa868-b55e-439e-8382-23548e5a7041","attributes":{"dimension":1,"axis":{"id":"0f0cca9d-1cfe-4918-b27f-b72a72f4d151"}}},{"type":"object","name":"Legend","id":"97314c61-b471-4f34-8adb-39faf587183b","attributes":{"items":[{"type":"object","name":"LegendItem","id":"b7553d2e-7ce4-443f-ae2f-dfdfa503b888","attributes":{"label":{"type":"field","field":"designation"},"renderers":[{"id":"48b2580d-d01a-4b54-a532-31c51da77036"}]}}]}}]}}]}}]}},{"type":"object","name":"panel.models.comm_manager.CommManager","id":"6ed8794e-fad5-49f4-8c73-ee68dc29a4ca","attributes":{"plot_id":"ff448e6d-6846-46c4-b3af-6359c2945424","comm_id":"c1857fb8078a4bd1958278cc87e8e6d0","client_comm_id":"9e52f3f2d33640968b6022814b313d57"}}],"defs":[{"type":"model","name":"ReactiveHTML1"},{"type":"model","name":"FlexBox1","properties":[{"name":"align_content","kind":"Any","default":"flex-start"},{"name":"align_items","kind":"Any","default":"flex-start"},{"name":"flex_direction","kind":"Any","default":"row"},{"name":"flex_wrap","kind":"Any","default":"wrap"},{"name":"justify_content","kind":"Any","default":"flex-start"}]},{"type":"model","name":"FloatPanel1","properties":[{"name":"config","kind":"Any","default":{"type":"map"}},{"name":"contained","kind":"Any","default":true},{"name":"position","kind":"Any","default":"right-top"},{"name":"offsetx","kind":"Any","default":null},{"name":"offsety","kind":"Any","default":null},{"name":"theme","kind":"Any","default":"primary"},{"name":"status","kind":"Any","default":"normalized"}]},{"type":"model","name":"GridStack1","properties":[{"name":"mode","kind":"Any","default":"warn"},{"name":"ncols","kind":"Any","default":null},{"name":"nrows","kind":"Any","default":null},{"name":"allow_resize","kind":"Any","default":true},{"name":"allow_drag","kind":"Any","default":true},{"name":"state","kind":"Any","default":[]}]},{"type":"model","name":"drag1","properties":[{"name":"slider_width","kind":"Any","default":5},{"name":"slider_color","kind":"Any","default":"black"},{"name":"value","kind":"Any","default":50}]},{"type":"model","name":"click1","properties":[{"name":"terminal_output","kind":"Any","default":""},{"name":"debug_name","kind":"Any","default":""},{"name":"clears","kind":"Any","default":0}]},{"type":"model","name":"FastWrapper1","properties":[{"name":"object","kind":"Any","default":null},{"name":"style","kind":"Any","default":null}]},{"type":"model","name":"NotificationAreaBase1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0}]},{"type":"model","name":"NotificationArea1","properties":[{"name":"js_events","kind":"Any","default":{"type":"map"}},{"name":"notifications","kind":"Any","default":[]},{"name":"position","kind":"Any","default":"bottom-right"},{"name":"_clear","kind":"Any","default":0},{"name":"types","kind":"Any","default":[{"type":"map","entries":[["type","warning"],["background","#ffc107"],["icon",{"type":"map","entries":[["className","fas fa-exclamation-triangle"],["tagName","i"],["color","white"]]}]]},{"type":"map","entries":[["type","info"],["background","#007bff"],["icon",{"type":"map","entries":[["className","fas fa-info-circle"],["tagName","i"],["color","white"]]}]]}]}]},{"type":"model","name":"Notification","properties":[{"name":"background","kind":"Any","default":null},{"name":"duration","kind":"Any","default":3000},{"name":"icon","kind":"Any","default":null},{"name":"message","kind":"Any","default":""},{"name":"notification_type","kind":"Any","default":null},{"name":"_destroyed","kind":"Any","default":false}]},{"type":"model","name":"TemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"BootstrapTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]},{"type":"model","name":"MaterialTemplateActions1","properties":[{"name":"open_modal","kind":"Any","default":0},{"name":"close_modal","kind":"Any","default":0}]}]}};
      var render_items = [{"docid":"362dc27d-4ba0-4644-a785-222a07aa0b97","roots":{"ff448e6d-6846-46c4-b3af-6359c2945424":"a162233f-57ea-4f32-83d3-1b1d49e8c764"},"root_ids":["ff448e6d-6846-46c4-b3af-6359c2945424"]}];
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
