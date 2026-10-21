"""Interactive exploration tools for chimera summary metrics.

This module provides functions to:
- Load chimera summary data from a ResultsDb SQLite database
- Create interactive Bokeh plots showing metric values vs transition date
- Allow metric selection via dropdown widgets with multiple info label and
  summary metric selection (overplotted with different colors and linestyles)

Example usage in a Jupyter notebook:
    %aimport chimera_explore
    import bokeh.io
    bokeh.io.output_notebook()
    from bokeh.plotting import show

    # Load summary data
    db_path = '/workspace/tmp/chimera_2026-05-21/resultsDb_sqlite.db'
    summary_df, unique_metrics = chimera_explore.load_chimera_summary(db_path)

    # Create interactive plot
    plot = chimera_explore.make_metric_selector_plot(summary_df, unique_metrics)

    # Display using bokeh.plotting.show()
    show(plot)

Note: dayObs values (YYYYMMDD format) are converted to datetime objects for
proper time-based plotting, since dayObs is not a linear integer.
"""

import json
import os
import re as re_module

import bokeh.core.enums
import bokeh.events
import bokeh.io
import bokeh.layouts
import bokeh.models
import bokeh.palettes
import bokeh.plotting
import click
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

from schedview.collect.progress import load_chimera_summary
from schedview.plot.progress import make_metric_selector_plot, save_metric_data_json

@click.command()
@click.argument("db_path", type=click.Path(exists=True))
@click.argument("output_html", type=click.Path())
@click.option("--build-date", "-d", default=None, help="Build date string for heading. Defaults to current datetime.")
@click.option("--title", "-t", default="Chimera Metric Explorer", help="HTML page title.")
def main(db_path, output_html, build_date, title):
    """Generate an interactive Chimera Metric Explorer HTML file.

    DB_PATH is the path to a ResultsDb SQLite database containing chimera runs.
    OUTPUT_HTML is the path where the output HTML file will be written.
    A companion JSON data file is written alongside the HTML file.
    """
    if build_date is None:
        build_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_df, unique_metrics = load_chimera_summary(db_path)

    if output_html.endswith('.html'):
        json_path = output_html[:-5] + '_data.json'
    else:
        json_path = output_html + '_data.json'

    save_metric_data_json(summary_df, unique_metrics, json_path)

    data_json_url = os.path.basename(json_path)
    plot = make_metric_selector_plot(summary_df, unique_metrics, build_date, data_json_url=data_json_url)
    bokeh.io.output_file(filename=output_html, title=f"{title} (built: {build_date})")
    bokeh.io.save(plot)
    click.echo(f"Saved to {output_html}")
    click.echo(f"Data written to {json_path}")


if __name__ == "__main__":
    main()
