from pathlib import Path

import bokeh.command.bootstrap


def start_app(app_name):
    """Start a bokeh app.

    Parameters
    ----------
    app_name : `str`
        The name of the bokeh app (and submodule of schedview.app)

    """
    base_dir = Path(__file__).resolve().parent
    app_dir = Path(base_dir, app_name).as_posix()
    bokeh.command.bootstrap.main(["bokeh", "serve", app_dir])


def sched_maps():
    """Start the sched_maps app."""
    start_app("sched_maps")


def metric_maps():
    """Start the metric_maps app."""
    start_app("metric_maps")
