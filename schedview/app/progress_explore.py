"""Standalone summary-progress reports and independent records JSON export.

The plot command embeds data from local SQLite databases. HTTP(S) URLs and
page-relative paths ending in ``.json`` remain external: serve the page and
JSON over HTTP(S), with appropriate CORS permissions for cross-origin data.
External data change only on browser reload. Use ``--input-kind`` to override
suffix-based classification, for example for a database named ``results.json``
or a JSON endpoint without a suffix. Bokeh resources use the CDN.
"""

import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlsplit

import click
from bokeh.embed import file_html
from bokeh.resources import CDN

from schedview.collect.progress import load_summary_metrics, validate_summary_metrics
from schedview.plot.progress import make_summary_progress_plot


def _check_output_path(input_path: str | Path, output_path: str) -> None:
    original = Path(input_path).expanduser()
    destination = Path(output_path)
    if destination.resolve() == original.resolve() or (
        destination.exists() and original.exists() and destination.samefile(original)
    ):
        raise ValueError(f"Output {output_path!r} refers to the input data; refusing to overwrite it")


@click.command(name="make_summary_progress_data")
@click.argument("db_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.argument("json_path", type=click.Path(dir_okay=False))
def make_summary_progress_data(db_path: str, json_path: str) -> None:
    """Write validated summary records from DB_PATH to JSON_PATH.

    Dates are calendar midnight in epoch milliseconds. Missing and nonfinite
    measurements become JSON null; finite scalars use pandas' maximum supported
    precision (15 decimal places). No selector catalog or envelope is written.
    """
    try:
        _check_output_path(db_path, json_path)
        summary_metrics = load_summary_metrics(db_path)
        validate_summary_metrics(summary_metrics)
        records = summary_metrics.copy()
        records["summary_value"] = records["summary_value"].replace(
            [float("inf"), float("-inf")], float("nan")
        )
        records.to_json(json_path, orient="records", date_format="epoch", date_unit="ms", double_precision=15)
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        raise click.ClickException(f"Cannot export {db_path!r} to {json_path!r}: {error}") from error
    click.echo(f"Data written to {json_path}")


@click.command(name="make_summary_progress_plot")
@click.argument("summary_metrics")
@click.argument("page_path", type=click.Path(dir_okay=False))
@click.option(
    "--input-kind",
    type=click.Choice(["auto", "database", "json-url"]),
    default="auto",
    show_default=True,
    help="Auto: HTTP(S) and page-relative .json paths are URLs; other paths are databases.",
)
@click.option(
    "--title", "-t", default="Summary Progress Explorer", show_default=True, help="HTML page title."
)
def make_summary_progress_plot_cli(summary_metrics: str, page_path: str, input_kind: str, title: str) -> None:
    """Write a standalone progress page to PAGE_PATH from SUMMARY_METRICS.

    SUMMARY_METRICS is a local SQLite database or external JSON URL. URLs are
    passed through unchanged without reading them on this machine. Local path
    collisions are checked to avoid overwriting page-relative JSON inputs.
    Relative URLs resolve against the served page, not the current directory.
    Database input embeds records and does not create a companion JSON file.
    """
    try:
        if input_kind == "auto":
            parsed = urlsplit(summary_metrics)
            is_url = parsed.scheme.lower() in {"http", "https"} or (
                not parsed.scheme and parsed.path.lower().endswith(".json")
            )
        else:
            is_url = input_kind == "json-url"
        if not is_url:
            _check_output_path(summary_metrics, page_path)
        else:
            parsed = urlsplit(summary_metrics)
            if not parsed.scheme and not parsed.netloc:
                _check_output_path(Path(page_path).parent / unquote(parsed.path), page_path)
        records = summary_metrics if is_url else load_summary_metrics(summary_metrics)
        plot = make_summary_progress_plot(records)
        Path(page_path).write_text(file_html(plot, CDN, title=title), encoding="utf-8")
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        raise click.ClickException(
            f"Cannot create {page_path!r} from {summary_metrics!r}: {error}"
        ) from error
    click.echo(f"Saved to {page_path}")


if __name__ == "__main__":
    make_summary_progress_plot_cli()
