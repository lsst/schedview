Architecture
============

Context and scope
-----------------

- Data origins
- Data sources
- Data processing
- General plotting and visualization tools
- Dashboard tools
- Environments

Visualization Generation and ``schedview`` Components
-----------------------------------------------------

``schedview`` is designed to manage the process of generating a figure in a few distinct stages or layers.
``schedview``'s submodules organize the code according to these stages:

Collection
  In the collection stage, ``schedview`` creates instances of ``python`` objects that hold the data to be visualized.
  The ``schedview.collect`` submodule provides the code used for this stage.
  Different implementations or configurations of the collection functionality may be required in different environemnts.
  For example, the direct access to the EFD may be available to ``schedview`` when being run at the observatory but maybe not when running at an RSP on an astronomer's laptop, but the same data may be available through different mechanisms in these other environments.
  All code that depends on specific access mechanisms that can potentially vary from one site to another should be encapsulated in ``schedview.collect``.
  No code that should be reused when the source of data is changed should be included in ``schedview.collect``.

Computation
  Sometimes, the data to be plotted is not exactly as provided by external sources, or can be generated entirely computationally.
  For example, sunrise and sunset times can be generated entirely from software dependencies.
  The ``schedview.compute`` submodule provides the code used for this stage.
  In general, code included in ``schedview.compute`` should be limited, and closely tied to the visualizations.
  It should depend neither on the data access mechanism, nor on the plotting tools used to actually create the visualization.
  More genenerally applicable analysis code will be more appropriately packaged outside of ``schedview``, for example in ``maf``.
  Either simple wrappers around this external code (in ``schedview.compute``) or the output of data that performs these computations read (by ``schedview.collect``) when the results are needed by ``schedview``.

Plotting
  The plotting stage creates the plots themselves, taking the data provided by the collection and computation stages and producing a figure or document that can be displayed to a user.
  The ``schedview.plot`` submodule provides code used for this stage.
  It should be limited to the specific application of plotting tools (e.g. ``bokeh`` or ``matplotlib``) to specific data sets provided by ``schedview.collect`` or ``schedview.compute``.
  ``schedview`` is not intended to be a repository for tools to make arbitrary plots, but rather specific applications of plots (perhaps with many configurable paramaters).
  Plotting utilities of more general usage should be packaged separaterly, outside of ``schedview``.
  For example, the separate ``uranography`` contains tools for making sky maps; ``schedview`` contains functions that use ``uranography`` to plot survey basis functions.

Dashboards
  It is often helpful to integrate multiple visualizations into a unified, standardized user display: a dashboard.
  The ``schedview.app`` submodule provides programs that combine collection, computation, and plotting tools to prodive such a dashboard in a web application.
