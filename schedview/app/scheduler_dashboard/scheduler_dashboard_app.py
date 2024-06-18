#! /usr/bin/env python

# This file is part of schedview.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""schedview docstring"""

import argparse
import importlib.resources
import os

# Filter the astropy warnings swamping the terminal.
import warnings
from glob import glob

import panel as pn
from astropy.utils.exceptions import AstropyWarning
from panel.io.loading import start_loading_spinner, stop_loading_spinner

from schedview.app.scheduler_dashboard.constants import (
    LFA_DATA_DIR,
    LOGO,
    PACKAGE_DATA_DIR,
    h1_stylesheet,
    h2_stylesheet,
)
from schedview.app.scheduler_dashboard.lfa_scheduler_snapshot_dashboard import LFASchedulerSnapshotDashboard
from schedview.app.scheduler_dashboard.restricted_scheduler_snapshot_dashboard import (
    RestrictedSchedulerSnapshotDashboard,
)
from schedview.app.scheduler_dashboard.unrestricted_scheduler_snapshot_dashboard import (
    SchedulerSnapshotDashboard,
)

# Filter astropy warning that's filling the terminal with every update.
warnings.filterwarnings("ignore", category=AstropyWarning)


pn.extension(
    "tabulator",
    sizing_mode="stretch_width",
    notifications=True,
)


# ------------------------------------------------------------ Create dashboard.
def scheduler_app(date_time=None, scheduler_pickle=None, **kwargs):
    """Create a dashboard with grids of Param parameters, Tabulator widgets,
    and Bokeh plots.

    Parameters
    ----------
    widget_datetime : `datetime` or `date`, optional
        The date/datetime of interest. The default is None.
    scheduler_pickle : `str`, optional
        A filepath or URL for the scheduler pickle. The default is None.

    Returns
    -------
    sched_app : `panel.layout.grid.GridSpec`
        The dashboard.
    """
    # Initialize the dashboard layout.
    sched_app = pn.GridSpec(
        sizing_mode="stretch_both",
        max_height=1000,
    ).servable()

    # Bools for different dashboard modes.
    from_urls = False
    data_dir = None
    from_lfa = False

    if "data_from_urls" in kwargs.keys():
        from_urls = kwargs["data_from_urls"]
        del kwargs["data_from_urls"]

    if "data_dir" in kwargs.keys():
        data_dir = kwargs["data_dir"]
        del kwargs["data_dir"]

    if "lfa" in kwargs.keys():
        from_lfa = kwargs["lfa"]
        del kwargs["lfa"]

    scheduler = None

    # Accept pickle files from url or any path.
    if from_urls:
        scheduler = SchedulerSnapshotDashboard()
        # Read pickle and time if provided to the function in a notebook.
        # It will be overridden if the dashboard runs in an app.
        if date_time is not None:
            scheduler.widget_datetime = date_time

        if scheduler_pickle is not None:
            scheduler.scheduler_fname = scheduler_pickle

        # Sync url parameters only if the files aren't restricted.
        if pn.state.location is not None:
            pn.state.location.sync(
                scheduler,
                {
                    "scheduler_fname": "scheduler",
                    "nside": "nside",
                    "url_mjd": "mjd",
                },
            )

    # Load pickles from S3 bucket.
    elif from_lfa:
        scheduler = LFASchedulerSnapshotDashboard()

    # Restrict files to data_directory.
    else:
        scheduler = RestrictedSchedulerSnapshotDashboard(data_dir=data_dir)
        # data_loading_widgets = {
        #     "widget_datetime": pn.widgets.DatetimePicker,
        # }

    # Show dashboard as busy when scheduler.show_loading_spinner is True.
    @pn.depends(loading=scheduler.param.show_loading_indicator, watch=True)
    def update_loading(loading):
        """Update the dashboard's loading indicator based on the
        'show_loading_indicator' parameter.

        Parameters
        ----------
        loading : `bool`
            Indicates whether the loading indicator should be shown.
        """
        if loading:
            scheduler.logger.debug("DASHBOARD START LOADING")
            start_loading_spinner(sched_app)
        else:
            scheduler.logger.debug("DASHBOARD STOP LOADING")
            stop_loading_spinner(sched_app)

    # Define reset button.
    reset_button = pn.widgets.Button(
        name="Restore Loading Conditions",
        icon="restore",
        icon_size="16px",
        description=" Restore initial date, table ordering and map properties.",
    )

    # Reset dashboard to loading conditions.
    def handle_reload_pickle(event):
        """Reset the dashboard to its initial loading conditions.

        Parameters
        ----------
        event : `pn.widgets.Button`
            The Button widget instance that triggered the function call.
        """
        scheduler.logger.debug("RELOAD PICKLE")
        scheduler.nside = 16
        scheduler.color_palette = "Viridis256"
        if scheduler.scheduler_fname == "":
            scheduler.clear_dashboard()
        else:
            scheduler._update_scheduler_fname()

    # Set function trigger.
    reset_button.on_click(handle_reload_pickle)

    # ------------------------------------------------------ Dashboard layout.
    # Dashboard title.
    sched_app[0:8, :] = pn.Row(
        pn.Column(
            pn.Spacer(height=4),
            pn.pane.Str(
                "Scheduler Dashboard",
                height=20,
                stylesheets=[h1_stylesheet],
            ),
            scheduler.dashboard_subtitle,
        ),
        pn.layout.HSpacer(),
        pn.pane.PNG(
            LOGO,
            sizing_mode="scale_height",
            align="center",
            margin=(5, 5, 5, 5),
        ),
        sizing_mode="stretch_width",
        styles={"background": "#048b8c"},
    )
    # Parameter inputs (pickle, widget_datetime, tier)
    # as well as pickles date and telescope when running in LFA.
    sched_app[8 : scheduler.data_params_grid_height, 0:21] = pn.Param(
        scheduler,
        parameters=scheduler.data_loading_parameters,
        widgets=scheduler.data_loading_widgets,
        name="Select pickle file, date and tier.",
    )
    # Reset button.
    sched_app[scheduler.data_params_grid_height : scheduler.data_params_grid_height + 6, 3:15] = pn.Row(
        reset_button
    )
    # Summary table and header.
    sched_app[8 : scheduler.data_params_grid_height + 6, 21:67] = pn.Row(
        pn.Spacer(width=10),
        pn.Column(
            pn.Spacer(height=10),
            pn.Row(
                scheduler.summary_table_heading,
                styles={"background": "#048b8c"},
            ),
            pn.param.ParamMethod(scheduler.publish_summary_widget, loading_indicator=True),
        ),
        pn.Spacer(width=10),
    )
    # Reward table and header.
    sched_app[scheduler.data_params_grid_height + 6 : scheduler.data_params_grid_height + 45, 0:67] = pn.Row(
        pn.Spacer(width=10),
        pn.Column(
            pn.Spacer(height=10),
            pn.Row(
                scheduler.reward_table_heading,
                styles={"background": "#048b8c"},
            ),
            pn.param.ParamMethod(scheduler.publish_reward_widget, loading_indicator=True),
        ),
        pn.Spacer(width=10),
    )
    # Map display and header.
    sched_app[8 : scheduler.data_params_grid_height + 25, 67:100] = pn.Column(
        pn.Spacer(height=10),
        pn.Row(
            scheduler.map_title,
            styles={"background": "#048b8c"},
        ),
        pn.param.ParamMethod(scheduler.publish_sky_map, loading_indicator=True),
    )
    # Map display parameters (map, nside, color palette).
    sched_app[scheduler.data_params_grid_height + 32 : scheduler.data_params_grid_height + 45, 67:100] = (
        pn.Param(
            scheduler,
            widgets={
                "survey_map": {"type": pn.widgets.Select, "width": 250},
                "nside": {"type": pn.widgets.Select, "width": 150},
                "color_palette": {"type": pn.widgets.Select, "width": 100},
            },
            parameters=["survey_map", "nside", "color_palette"],
            show_name=False,
            default_layout=pn.Row,
        )
    )
    # Debugging collapsable card.
    sched_app[scheduler.data_params_grid_height + 45 : scheduler.data_params_grid_height + 52, :] = pn.Card(
        scheduler._debugging_messages,
        header=pn.pane.Str("Debugging", stylesheets=[h2_stylesheet]),
        header_color="white",
        header_background="#048b8c",
        sizing_mode="stretch_width",
        collapsed=False,
    )

    return sched_app


def parse_arguments():
    """Parse commandline arguments to read data directory if provided.
    """
    parser = argparse.ArgumentParser(description="On-the-fly Rubin Scheduler dashboard")
    default_data_dir = f"{LFA_DATA_DIR}/*" if os.path.exists(LFA_DATA_DIR) else PACKAGE_DATA_DIR

    parser.add_argument(
        "--data_dir",
        "-d",
        type=str,
        default=default_data_dir,
        help="The base directory for data files.",
    )

    parser.add_argument(
        "--data_from_urls",
        action="store_true",
        help="Let the user specify URLs from which to load data. THIS IS NOT SECURE.",
    )

    parser.add_argument(
        "--lfa",
        action="store_true",
        help="Loads pickle files from S3 buckets in LFA",
    )

    args = parser.parse_args()

    if len(glob(args.data_dir)) == 0 and not args.data_from_urls:
        args.data_dir = PACKAGE_DATA_DIR

    if args.lfa and len(glob(LFA_DATA_DIR)) == 0:
        args.data_dir = PACKAGE_DATA_DIR

    scheduler_app_params = args.__dict__

    return scheduler_app_params


def main():
    """Start the scheduler dashboard server.

    Parse command-line arguments, set up the scheduler application,
    and serve it using Panel (pn).

    Notes
    -----
    Use environment variable 'SCHEDULER_SNAPSHOT_DASHBOARD_PORT' for port
    configuration. Default to port 8888 if not set.
    """

    print("Starting scheduler dashboard.")
    commandline_args = parse_arguments()

    if "SCHEDULER_SNAPSHOT_DASHBOARD_PORT" in os.environ:
        scheduler_port = int(os.environ["SCHEDULER_SNAPSHOT_DASHBOARD_PORT"])
    else:
        scheduler_port = 8888

    assets_dir = os.path.join(importlib.resources.files("schedview"), "app", "scheduler_dashboard", "assets")

    def scheduler_app_with_params():
        return scheduler_app(**commandline_args)

    app_dict = {"dashboard": scheduler_app_with_params}
    prefix = "/schedview-snapshot"
    print(f"prefix: {prefix}, app_dict keys = {list(app_dict.keys())}")

    pn.serve(
        app_dict,
        port=scheduler_port,
        title="Scheduler Dashboard",
        show=False,
        prefix=prefix,
        start=True,
        autoreload=True,
        # threaded=True,
        static_dirs={"assets": assets_dir},
    )


if __name__ == "__main__":
    main()
