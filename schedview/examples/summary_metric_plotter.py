"""Command-line tool to generate a Summary Metric Explorer HTML file.

Usage::

    python -m schedview.examples.summary_metric_plotter \\
        /path/to/resultsDb_sqlite.db output.html
"""

import os
from datetime import datetime

import bokeh.io
import click

from schedview.collect.maf_summary import load_maf_summary
from schedview.plot.maf_summary import make_metric_selector_plot, save_metric_data_json


def make_summary_metric_plot(
    db_path: str,
    output_html: str,
    build_date: str | None = None,
    title: str = "Summary Metric Explorer",
    run_name_pattern: str = "chimera_%",
) -> None:
    """Generate an interactive Summary Metric Explorer HTML file.

    Parameters
    ----------
    db_path : str
        Path to the ResultsDb SQLite database file.
    output_html : str
        Path for the output HTML file.
    build_date : str or None, optional
        Build date string for the heading.  If None, uses current datetime.
    title : str, optional
        HTML page title.
    run_name_pattern : str, optional
        SQL LIKE pattern to filter run names.
    """
    if build_date is None:
        build_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collect
    summary_df, unique_metrics = load_maf_summary(db_path, run_name_pattern)

    # Derive JSON path from HTML path
    if output_html.endswith(".html"):
        json_path = output_html[:-5] + "_data.json"
    else:
        json_path = output_html + "_data.json"

    # Save JSON data file
    save_metric_data_json(summary_df, unique_metrics, json_path)

    # Plot
    data_json_url = os.path.basename(json_path)
    plot = make_metric_selector_plot(
        summary_df, unique_metrics, build_date, data_json_url=data_json_url
    )

    # Report
    bokeh.io.output_file(
        filename=output_html, title=f"{title} (built: {build_date})"
    )
    bokeh.io.save(plot)

    print(f"Saved to {output_html}")
    print(f"Data written to {json_path}")


@click.command()
@click.argument("db_path", type=click.Path(exists=True))
@click.argument("output_html", type=click.Path())
@click.option(
    "--build-date",
    "-d",
    default=None,
    help="Build date string for heading. Defaults to current datetime.",
)
@click.option(
    "--title",
    "-t",
    default="Summary Metric Explorer",
    help="HTML page title.",
)
@click.option(
    "--run-name-pattern",
    "-p",
    default="chimera_%",
    help="SQL LIKE pattern to filter run names.",
)
def main(db_path, output_html, build_date, title, run_name_pattern):
    """Generate an interactive Summary Metric Explorer HTML file.

    DB_PATH is the path to a ResultsDb SQLite database.
    OUTPUT_HTML is the path where the output HTML file will be written.
    A companion JSON data file is written alongside the HTML file.
    """
    make_summary_metric_plot(db_path, output_html, build_date, title, run_name_pattern)


if __name__ == "__main__":
    main()
