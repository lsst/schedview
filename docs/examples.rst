Examples
========

Single-figure report generation tools
-------------------------------------

The examples submodule of ``schedview`` contains a collection of ``python``
executables demonstrating minimal pipelines that produce figures generated by
``schedview`` tools. These tools create ``html``, ``png``, or ``Markdown``
files with just a single figure. There are not generally intended to be used
to do produce these files (although they will do such), but rather as
minimal demonstrations of how to generate each type of figure.

For example, consider ``schedview/examples/visitmap.py``, show in its entirety
here:

.. code:: python3

  import argparse
  import datetime

  import astropy.utils.iers
  import bokeh.embed
  import bokeh.io
  import bokeh.models
  import pandas as pd
  import uranography.api
  from rubin_scheduler.scheduler.model_observatory.model_observatory import ModelObservatory

  import schedview.compute.visits
  import schedview.plot
  from schedview.dayobs import DayObs


  def make_visit_map(
      iso_date: str | datetime.date,
      visit_source: str,
      nside: int = 16,
      map_classes=[uranography.api.ArmillarySphere, uranography.api.Planisphere],
      report: None | str = None,
  ) -> bokeh.models.UIElement:
      """Make a visit map.

      Parameters
      ----------
      iso_date : `str`
          Local calendar date of the evening on which the night starts,
          in YYYY-MM-DD (ISO 8601) format.
      visit_source : `str`
          Instrument or baseline version number.
      nside: `int`, optional
          The nside of the map to show, by default 8.
      map_classes: `list`, optional
          A list of uranography map classes to use, by default
          `[uranography.api.ArmillarySphere, uranography.api.Planisphere]`.
      report : `None` | `str`, optional
          Report file name, by default ``None`` (to not write to a file).

      Returns
      -------
      result : `bokeh.models.UIElement`
          The bokeh plot object with the map(s) of visits.
      """

      # Parameters
      day_obs: DayObs = DayObs.from_date(iso_date)

      # Collect
      visits: pd.DataFrame = schedview.collect.visits.read_visits(
          day_obs, visit_source, stackers=schedview.collect.visits.NIGHT_STACKERS
      )
      footprint = schedview.collect.footprint.get_footprint(nside)

      # Compute
      observatory: ModelObservatory = ModelObservatory(nside=nside, init_load_length=1)
      observatory.mjd = day_obs.mean_local_solar_midnight.mjd
      conditions = observatory.return_conditions()
      visits: pd.DataFrame = schedview.compute.visits.add_coords_tuple(visits)

      # Plot
      result: bokeh.models.UIElement = schedview.plot.visitmap.plot_visit_skymaps(
          visits, footprint, conditions, map_classes=map_classes
      )

      # Report
      if report is not None:
          with open(report, "w") as report_io:
              print(bokeh.embed.file_html(result), file=report_io)

      return result


  if __name__ == "__main__":
      parser = argparse.ArgumentParser(prog="visitmap", description="Make interactive maps of visits.")
      parser.add_argument("date", type=str, help="Evening YYYY-MM-DD")
      parser.add_argument(
          "visit_source", type=str, default="lsstcomcam", help="Instrument or baseline version number"
      )
      parser.add_argument("report", type=str, help="output file name")
      parser.add_argument("--nside", type=int, default=16, help="nside of map to show")
      args = parser.parse_args()

      astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"

      make_visit_map(args.date, args.visit_source, args.nside, report=args.report)

This executable dries the fill workflow to produce an interactive map of visits
on the sky for a night. It can be run thus:

.. code:: bash
  python schedview/examples/visitmap.py 2024-10-05 lsstcomcam myvisitmap.html

and it will create a file, ``myvisitmap.html``, that can be opened in a
browser and show an interactive sky map with the visits from the requested
night and instrument.

Note that the function ``make_visit_map`` defined in ``visitmap.py`` is
divided into sections that correspond to the high-level submodules that
implement ``schedview``'s architecture: collection, computation, plotting,
and reporting.
The other files in the same submodule show the same sequence, each with just
those elements needed for the specific figure being demonstrated.

Web applications/dashboards
---------------------------

The ``app`` submodule of the ``schedview.examples`` submodule contains a
handful of examples showing minimal web applications that show ``schedview``
figures.

* ``schedview/examples/app/visitmap.py`` shows a minimal dashboard using the highest level ``panel`` API. This API requires minimal code to create a dashboard, but is harder to structure cleanly.
* ``schedview/examples/app/visitmap.py`` shows a minimal dashboard using the ``Parameterized`` ``panel`` API, which is somewhat longer but recommended for long-term maintainability.
* ``schedview/examples/app/visits.py`` shows a sample dashboard that combunes a handful of different elements.
* ``schedview/examples/app/event_timeline.py`` show a second dashboard using the ``Parameterized`` ``panel`` API.
