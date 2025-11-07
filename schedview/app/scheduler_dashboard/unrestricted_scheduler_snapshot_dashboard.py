import logging
import os
import traceback

# Filter the astropy warnings swamping the terminal.
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import bokeh
import numpy as np
import panel as pn
import param
import rubin_scheduler.site_models
from astropy.time import Time
from bokeh.models import ColorBar, LinearColorMapper
from bokeh.models.widgets.tables import BooleanFormatter, HTMLTemplateFormatter, NumberFormatter
from lsst.resources import ResourcePath
from pandas import Timestamp
from pytz import timezone

# For the conditions.mjd bugfix.
from rubin_scheduler.scheduler.model_observatory import ModelObservatory

import schedview
import schedview.collect.scheduler_pickle
import schedview.compute.scheduler
import schedview.compute.survey
import schedview.param
import schedview.plot.survey
from schedview.app.scheduler_dashboard.constants import (
    COLOR_PALETTES,
    DEFAULT_COLOR_PALETTE,
    DEFAULT_NSIDE,
    DEFAULT_TIMEZONE,
    h2_stylesheet,
    h3_stylesheet,
)
from schedview.app.scheduler_dashboard.utils import (
    get_sky_brightness_date_bounds,
    localize_scheduler_url,
    url_formatter,
)


class SchedulerSnapshotDashboard(param.Parameterized):
    """A Parametrized container for parameters, data, and panel objects for the
    scheduler dashboard working in flexible (insecure mode) where data files
    are loaded from any path or URL.
    """

    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
    Such a pickle file can either be of an instance of a subclass of
    rubin_scheduler.scheduler.schedulers.CoreScheduler, or a tuple of the form
    (scheduler, conditions), where scheduler is an instance of a subclass of
    rubin_scheduler.scheduler.schedulers.CoreScheduler, and conditions is an
    instance of rubin_scheduler.scheduler.conditions.Conditions.
    """

    # Get available skybrightness_pre date range.
    (mjd_min, mjd_max) = get_sky_brightness_date_bounds()
    # Convert astropy times to iso format to be
    # used as bounds for datetime parameter.
    date_bounds = (mjd_min.to_datetime(), mjd_max.to_datetime())

    # Param parameters that are modifiable by user actions.
    scheduler_fname = param.String(
        default="",
        label="Scheduler snapshot file",
        doc=scheduler_fname_doc,
        precedence=3,
    )
    widget_datetime = param.Date(
        default=date_bounds[0],
        label="Date and time (UTC)",
        doc=f"Select dates between {date_bounds[0]} and {date_bounds[1]}",
        bounds=date_bounds,
        precedence=4,
    )
    # mjd date passed as a url path parameter when
    # dashboard operates in --data_from_urls mode.
    url_mjd = param.Number(default=None)
    widget_tier = param.Selector(
        default="",
        objects=[""],
        label="Tier",
        doc="The label for the first index into the CoreScheduler.survey_lists.",
        precedence=5,
    )
    survey_map = param.Selector(
        default="reward",
        objects=["reward"],
        doc="Sky brightness maps, non-scalar rewards and survey reward map.",
    )
    nside = param.ObjectSelector(
        default=DEFAULT_NSIDE,
        objects=[2, 4, 8, 16, 32, 64],
        label="Map resolution (nside)",
        doc="",
    )
    color_palette = param.Selector(default=DEFAULT_COLOR_PALETTE, objects=COLOR_PALETTES, doc="")
    summary_widget = param.Parameter(default=None, doc="")
    reward_widget = param.Parameter(default=None, doc="")
    show_loading_indicator = param.Boolean(default=False)

    # Param parameters (used in depends decoraters and trigger calls).
    _publish_summary_widget = param.Parameter(None)
    _publish_reward_widget = param.Parameter(None)
    _publish_map = param.Parameter(None)
    _update_headings = param.Parameter(None)
    _update_chosen_survey = param.Parameter(None)
    _debugging_message = param.Parameter(None)

    # Non-Param parameters storing Panel pane objects.
    debug_pane = None
    dashboard_subtitle_pane = None
    summary_table_heading_pane = None
    reward_table_heading_pane = None
    map_title_pane = None
    chosen_survey_label_pane = None

    # Non-Param internal parameters.
    _mjd = None
    _tier = None
    _survey = 0
    _reward = -1
    _survey_name = ""
    _reward_name = ""
    _map_name = ""
    _scheduler = None
    _conditions = None
    _reward_df = None
    _scheduler_summary_df = None
    _survey_maps = None
    _survey_reward_df = None
    _sky_map_base = None
    _debug_string = ""
    _display_reward = False
    _display_dashboard_data = False

    # This boolean variable prevents unwanted triggering
    # of Param functions when updating watched variables.
    _do_not_trigger_update = True

    _summary_widget_height = 220
    _reward_widget_height = 400

    # Data loading parameters in both restricted and URL modes.
    data_loading_parameters = ["scheduler_fname", "widget_datetime", "widget_tier"]
    # Set the data loading parameter section height in both
    # restricted and URL modes.
    # This will be used to adjust the layout of other sections
    # in the grid.
    data_params_grid_height = 30

    # Set specific widget properties for data loading parameters
    # in URL and restricted modes.
    data_loading_widgets = {
        "scheduler_fname": {
            "placeholder": "filepath or URL of pickle",
        },
        "widget_datetime": pn.widgets.DatetimePicker,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self.config_logger()

    def config_logger(self, logger_name="schedule-snapshot"):
        """Configure the logger.

        Parameters
        ----------
        logger_name : `str`
            The name of the logger.
        """

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)

        log_stream_handler = None
        if self.logger.hasHandlers():
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    log_stream_handler = handler

        if log_stream_handler is None:
            log_stream_handler = logging.StreamHandler()

        log_stream_formatter = logging.Formatter("%(asctime)s: %(message)s")
        log_stream_handler.setFormatter(log_stream_formatter)
        self.logger.addHandler(log_stream_handler)

    # ----------------------------------------------------------- User actions.
    # The following set of functions are triggered when the user
    # updates one of the Parameters via the UI. The parameter
    # being "watched" is specified in the function decorators.
    #
    # These "watcher" functions call the relevant "internal
    # workings" functions (next section) to correctly update
    # the data and UI according to the user's behaviour.

    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler_fname(self):
        """Update the dashboard when a user enters a new filepath/URL."""
        self.logger.debug("UPDATE: scheduler file")
        self.show_loading_indicator = True
        self.clear_dashboard()

        if not self.read_scheduler():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        # Current fix for _conditions.mjd having different datatypes.
        if isinstance(self._conditions._mjd, np.ndarray):
            self._conditions._mjd = self._conditions._mjd[0]

        # Get mjd from pickle and set widget and URL to match.
        self._do_not_trigger_update = True
        self.url_mjd = self._conditions._mjd
        self.widget_datetime = Time(self._conditions._mjd, format="mjd").to_datetime()
        self._do_not_trigger_update = False

        if not self.make_scheduler_summary_df():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        self.create_summary_widget()
        self.param.trigger("_publish_summary_widget")

        self._do_not_trigger_update = True
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

        self._update_map_and_rewards()

    @param.depends("widget_datetime", watch=True)
    def _update_mjd_from_picker(self):
        """Update the dashboard when a datetime is input in widget."""
        if self._do_not_trigger_update:
            return

        self.logger.debug("UPDATE: mjd from date-picker")
        self.show_loading_indicator = True
        self.clear_dashboard()

        self._do_not_trigger_update = True
        self.url_mjd = Time(
            Timestamp(
                self.widget_datetime,
                tzinfo=ZoneInfo(DEFAULT_TIMEZONE),
            )
        ).mjd
        self._do_not_trigger_update = False
        self._mjd = self.url_mjd

        if not self.update_conditions():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if not self.make_scheduler_summary_df():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if self.summary_widget is None:
            self.create_summary_widget()
        else:
            self.update_summary_widget_data()
        self.param.trigger("_publish_summary_widget")

        self._do_not_trigger_update = True
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

        self._update_map_and_rewards()

    def _update_map_and_rewards(self):
        """Update map, reward widget and headings."""
        self.compute_survey_maps()
        self.survey_map = self.param["survey_map"].objects[-1]
        self._map_name = self.survey_map.split("@")[0].strip()

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

        self.make_reward_df()
        self.create_reward_widget()
        self.param.trigger("_publish_reward_widget")

        self._display_dashboard_data = True
        self._display_reward = False
        self.param.trigger("_update_headings")
        self.param.trigger("_update_chosen_survey")

        self.show_loading_indicator = False

    @param.depends("url_mjd", watch=True)
    def _update_mjd_from_url(self):
        """Update the dashboard when an mjd is input in URL."""
        if self._do_not_trigger_update:
            return

        self.logger.debug("UPDATE: mjd from url")
        self.show_loading_indicator = True
        self.clear_dashboard()

        self._do_not_trigger_update = True
        # Set Date Time widget to the mjd value set in URL.
        self.widget_datetime = Time(self.url_mjd, format="mjd").to_datetime()[0]
        self._do_not_trigger_update = False
        # Set the mjd value that's used across the dashboard.
        self._mjd = self.url_mjd

        if not self.update_conditions():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if not self.make_scheduler_summary_df():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if self.summary_widget is None:
            self.create_summary_widget()
        else:
            self.update_summary_widget_data()
        self.param.trigger("_publish_summary_widget")

        self._do_not_trigger_update = True
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

        self._update_map_and_rewards()

    @param.depends("widget_tier", watch=True)
    def _update_tier(self):
        """Update the dashboard when a user chooses a new tier."""
        if not self._display_dashboard_data:
            return
        self.logger.debug("UPDATE: tier")
        self._tier = self.widget_tier
        self._survey = 0
        self._survey_name = self._scheduler_summary_df[
            self._scheduler_summary_df["tier"] == self._tier
        ].reset_index()["survey"][self._survey]

        if self.summary_widget is None:
            self.create_summary_widget()
        else:
            self.update_summary_widget_data()
        self.param.trigger("_publish_summary_widget")

        self.compute_survey_maps()
        self._do_not_trigger_update = True
        self.survey_map = self.param["survey_map"].objects[-1]
        self._map_name = self.survey_map.split("@")[0].strip()
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

        self.make_reward_df()
        if self.reward_widget is None:
            self.create_reward_widget()
        else:
            self.update_reward_widget_data()
        self.param.trigger("_publish_reward_widget")

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

        self._display_reward = False
        self.param.trigger("_update_headings")

    @param.depends("summary_widget.selection", watch=True)
    def _update_survey(self):
        """Update the dashboard when a user selects a survey."""
        if self.summary_widget.selection == [] or self._do_not_trigger_update:
            return

        self.logger.debug("UPDATE: survey")
        self._survey = self.summary_widget.selection[0]
        self._survey_name = self._scheduler_summary_df[
            self._scheduler_summary_df["tier"] == self._tier
        ].reset_index()["survey"][self._survey]

        self.compute_survey_maps()
        self._do_not_trigger_update = True
        self.survey_map = self.param["survey_map"].objects[-1]
        self._map_name = self.survey_map.split("@")[0].strip()
        self._do_not_trigger_update = False

        self.make_reward_df()
        if self.reward_widget is None:
            self.create_reward_widget()
        else:
            self.update_reward_widget_data()
        self.param.trigger("_publish_reward_widget")

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

        self._display_reward = False
        self.param.trigger("_update_headings")

    @param.depends("reward_widget.selection", watch=True)
    def _update_reward(self):
        """Update the dashboard when a user selects a reward."""
        # Do not run code if no selection or when update flag is True.
        if self.reward_widget.selection == [] or self._do_not_trigger_update:
            return

        self.logger.debug("UPDATE: reward")
        self._reward = self.reward_widget.selection[0]
        self._reward_name = self._survey_reward_df["basis_function"][self._reward]

        # If reward is in survey maps, update survey maps drop-down.
        if any(self._reward_name in key for key in self._survey_maps):
            self._do_not_trigger_update = True
            self.survey_map = list(key for key in self._survey_maps if self._reward_name in key)[0]
            self._map_name = self.survey_map.split("@")[0].strip()
            self._do_not_trigger_update = False
        else:
            self.survey_map = ""

        self.update_sky_map_with_reward()
        self.param.trigger("_publish_map")

        self._display_reward = True
        self.param.trigger("_update_headings")

    @param.depends("survey_map", watch=True)
    def _update_survey_map(self):
        """Update the dashboard when a user chooses a new survey map."""
        # Don't run code during initial load or when updating tier or survey.
        if not self._display_dashboard_data or self._do_not_trigger_update:
            return

        # If user selects null map, do nothing.
        if self.survey_map == "":
            return

        self.logger.debug("UPDATE: survey map")
        # If selection is a reward map, reflect in reward table.
        self._do_not_trigger_update = True
        self._map_name = self.survey_map.split("@")[0].strip()
        if any(self._survey_reward_df["basis_function"].isin([self._map_name])):
            index = self._survey_reward_df["basis_function"].index[
                self._survey_reward_df["basis_function"].tolist().index(self._map_name)
            ]
            self.reward_widget.selection = [index]
        elif self.reward_widget is not None:
            self.reward_widget.selection = []
        self._do_not_trigger_update = False

        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

        self._display_reward = False
        self.param.trigger("_update_headings")

    @param.depends("nside", watch=True)
    def _update_nside(self):
        """Update the dashboard when a user chooses a new nside."""
        # Don't run code during initial load.
        if not self._display_dashboard_data:
            return

        self.logger.debug("UPDATE: nside")
        self.compute_survey_maps()

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

    @param.depends("color_palette", watch=True)
    def _update_color_palette(self):
        """Update the dashboard when a user chooses a new color palette."""
        self.logger.debug("UPDATE: color palette")
        if self._display_reward:
            self.update_sky_map_with_reward()
        else:
            self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

    # ------------------------------------------------------ Internal workings.
    # The following set of functions are called by the above
    # "watcher" functions. These functions are responsible
    # for correctly updating particular aspects of the
    # dashboard when the user makes a change in the UI.
    #
    # They are all self-contained functions (they do not call
    # other functions).
    #
    # The functions with decorators are those that are
    # returning objects to be displayed in the UI.

    def clear_dashboard(self):
        """Clear the dashboard for a new pickle or a new date."""
        self._debugging_message = "Starting to clear dashboard."

        self.summary_widget = None
        self._survey_reward_df = None
        self._sky_map_base = None
        self._display_dashboard_data = False
        self.reward_widget = None

        self.param.trigger("_publish_summary_widget")
        self.param.trigger("_publish_reward_widget")
        self.param.trigger("_publish_map")
        self.param.trigger("_update_headings")
        self.param.trigger("_update_chosen_survey")

        self.param["widget_tier"].objects = [""]
        self.param["survey_map"].objects = [""]

        self.widget_tier = ""
        self.survey_map = ""

        self._tier = ""
        self._survey = 0
        self._reward = -1

        self._debugging_message = "Finished clearing dashboard."

    def read_scheduler(self):
        """Load the scheduler and conditions objects from pickle file.

        Returns
        -------
        success : `bool`
            Record of success or failure of reading scheduler from file/URL.
        """
        try:
            self._debugging_message = "Requested scheduler path: " + self.scheduler_fname
            scheduler_path = (
                self.scheduler_fname
                if Path(self.scheduler_fname).is_file()
                else localize_scheduler_url(self.scheduler_fname)
            )
            self._debugging_message = "Starting to load scheduler from " + scheduler_path
            pn.state.notifications.info("Scheduler loading...", duration=0)

            os.environ["LSST_DISABLE_BUCKET_VALIDATION"] = "1"
            scheduler_resource_path = ResourcePath(scheduler_path)
            scheduler_resource_path.use_threads = False
            with scheduler_resource_path.as_local() as local_scheduler_resource:
                (scheduler, conditions) = schedview.collect.scheduler_pickle.read_scheduler(
                    local_scheduler_resource.ospath
                )

            self._scheduler = scheduler
            self._conditions = conditions

            self._debugging_message = "Finished loading scheduler."
            pn.state.notifications.clear()
            pn.state.notifications.success("Scheduler pickle loaded successfully!")

            return True

        except Exception:
            tb = traceback.format_exc(limit=-1)
            self._debugging_message = f"Cannot load scheduler from {self.scheduler_fname}: \n{tb}"
            pn.state.notifications.clear()
            pn.state.notifications.error(f"Cannot load scheduler from {self.scheduler_fname}", duration=0)

            self._scheduler = None
            self._conditions = None

            return False

    def update_conditions(self):
        """Update Conditions object.

        Returns
        -------
        success : `bool`
            Record of success of Conditions update.
        """
        if self._conditions is None:
            self._debugging_message = "Cannot update Conditions object as no Conditions object is loaded."

            return False

        try:
            self._debugging_message = "Starting to update Conditions object."
            pn.state.notifications.info("Updating Conditions object...", duration=0)

            # self._conditions.mjd = self._mjd

            # Use instance of ModelObservatory until Conditions
            # setting bug is fixed.
            if (
                not hasattr(self, "_model_observatory")
                or self._model_observatory.nside != self._scheduler.nside
            ):
                # Get weather conditions from pickle.
                wind_data = rubin_scheduler.site_models.ConstantWindData(
                    wind_speed=self._conditions.wind_speed,
                    wind_direction=self._conditions.wind_direction,
                )
                # Set seeing to fiducial site seeing.
                seeing_data = rubin_scheduler.site_models.ConstantSeeingData(0.69)
                # Create new MO instance.
                self._model_observatory = ModelObservatory(
                    nside=self._scheduler.nside,
                    init_load_length=1,
                    wind_data=wind_data,
                    seeing_data=seeing_data,
                )

            self._model_observatory.mjd = self._mjd
            self._conditions = self._model_observatory.return_conditions()
            self._scheduler.update_conditions(self._conditions)

            self._debugging_message = "Finished updating Conditions object."
            pn.state.notifications.clear()
            pn.state.notifications.success("Conditions object updated successfully")

            return True

        except Exception:
            tb = traceback.format_exc(limit=-1)
            self._debugging_message = f"Conditions object unable to be updated: \n{tb}"
            pn.state.notifications.clear()
            pn.state.notifications.error("Conditions object unable to be updated!", duration=0)

            return False

    def make_scheduler_summary_df(self):
        """Make the reward and scheduler summary dataframes.

        Returns
        -------
        success : `bool`
            Record of success of dataframe construction.
        """
        if self._scheduler is None:
            self._debugging_message = "Cannot update survey reward table as no pickle is loaded."

            return False

        try:
            self._debugging_message = "Starting to make scheduler summary dataframe."
            pn.state.notifications.info("Making scheduler summary dataframe...", duration=0)

            self._reward_df = self._scheduler.make_reward_df(self._conditions)
            scheduler_summary_df = schedview.compute.scheduler.make_scheduler_summary_df(
                self._scheduler,
                self._conditions,
                self._reward_df,
            )

            # Duplicate column and apply URL formatting to one of the columns.
            scheduler_summary_df["survey"] = scheduler_summary_df.loc[:, "survey_name_with_id"]
            scheduler_summary_df["survey_name_with_id"] = scheduler_summary_df.apply(
                url_formatter,
                axis=1,
                args=("survey_name_with_id", "survey_url"),
            )
            self._scheduler_summary_df = scheduler_summary_df

            tiers = self._scheduler_summary_df.tier.unique().tolist()
            self.param["widget_tier"].objects = tiers
            self.widget_tier = tiers[0]
            self._tier = tiers[0]
            self._survey = 0
            self._survey_name = self._scheduler_summary_df[
                self._scheduler_summary_df["tier"] == self._tier
            ].reset_index()["survey"][self._survey]

            self._debugging_message = "Finished making scheduler summary dataframe."
            pn.state.notifications.clear()
            pn.state.notifications.success("Scheduler summary dataframe updated successfully")

            return True

        except Exception:
            tb = traceback.format_exc(limit=-1)
            self._debugging_message = f"Scheduler summary dataframe unable to be updated: \n{tb}"
            pn.state.notifications.clear()
            pn.state.notifications.error("Scheduler summary dataframe unable to be updated!", duration=0)
            self._scheduler_summary_df = None

            return False

    def create_summary_widget(self):
        """Create Tabulator widget with scheduler summary dataframe."""
        if self._scheduler_summary_df is None:
            return

        self._debugging_message = "Starting to create summary widget."
        tabulator_formatter = {"survey_name_with_id": HTMLTemplateFormatter(template="<%= value %>")}
        columns = [
            "survey_index",
            "survey",
            "reward",
            "survey_name_with_id",
            "tier",
            "survey_url",
        ]
        titles = {
            "survey_index": "Index",
            "survey": "Survey",
            "reward": "Reward",
            "survey_name_with_id": "Docs",
        }
        widths = {
            "survey_index": "10%",
            "survey": "48%",
            "reward": "30%",
            "survey_name_with_id": "10%",
        }
        text_align = {
            "survey_index": "left",
            "survey": "left",
            "reward": "right",
            "survey_name_with_id": "center",
        }
        summary_widget = pn.widgets.Tabulator(
            self._scheduler_summary_df[self._scheduler_summary_df["tier"] == self._tier][columns],
            titles=titles,
            widths=widths,
            text_align=text_align,
            sortable={"survey_name_with_id": False},
            show_index=False,
            formatters=tabulator_formatter,
            disabled=True,
            selectable=1,
            hidden_columns=["tier", "survey_url"],
            sizing_mode="stretch_width",
            height=self._summary_widget_height,
        )
        self.summary_widget = summary_widget
        self._debugging_message = "Finished making summary widget."

    def update_summary_widget_data(self):
        """Update data for summary Tabulator widget."""
        self._debugging_message = "Starting to update summary widget."
        columns = [
            "survey_index",
            "survey",
            "reward",
            "survey_name_with_id",
            "tier",
            "survey_url",
        ]
        self.summary_widget._update_data(
            self._scheduler_summary_df[self._scheduler_summary_df["tier"] == self._tier][columns]
        )
        self._debugging_message = "Finished updating summary widget."

    @param.depends("_publish_summary_widget")
    def publish_summary_widget(self):
        """Publish the summary Tabulator widget
        to be displayed on the dashboard.

        Returns
        -------
        widget: `panel.widgets.Tabulator`
            Table of scheduler summary data.
        """
        if self.summary_widget is None:
            return "No summary available."
        else:
            self._debugging_message = "Publishing summary widget."
            return self.summary_widget

    def compute_survey_maps(self):
        """Compute survey maps and update drop-down selection."""
        if self._scheduler is None:
            self._debugging_message = "Cannot compute survey maps as no scheduler loaded."
            return
        if self._scheduler_summary_df is None:
            self._debugging_message = "Cannot compute survey maps as no scheduler summary made."
            return
        try:
            self._debugging_message = "Starting to compute survey maps."
            self._survey_maps = schedview.compute.survey.compute_maps(
                self._scheduler.survey_lists[int(self._tier[-1])][self._survey],
                self._conditions,
                np.int64(self.nside),
            )
            self.param["survey_map"].objects = [""] + list(self._survey_maps.keys())
            self._debugging_message = "Finished computing survey maps."

        except Exception:
            self._debugging_message = f"Cannot compute survey maps: \n{traceback.format_exc(limit=-1)}"
            pn.state.notifications.error("Cannot compute survey maps!", duration=0)

    def make_reward_df(self):
        """Make the survey reward dataframe."""
        if self._scheduler is None:
            self._debugging_message = "Cannot make reward dataframe as no scheduler loaded."
            return
        if self._scheduler_summary_df is None:
            self._debugging_message = "Cannot make reward dataframe as no scheduler summary made."
            return
        try:
            self._debugging_message = "Starting to make reward dataframe."
            # Survey has rewards.
            if self._reward_df.index.isin([(int(self._tier[-1]), self._survey)]).any():
                survey_reward_df = schedview.compute.survey.make_survey_reward_df(
                    self._scheduler.survey_lists[int(self._tier[-1])][self._survey],
                    self._conditions,
                    self._reward_df.loc[[(int(self._tier[-1]), self._survey)], :],
                )
                # Create accumulation order column.
                survey_reward_df["accum_order"] = range(len(survey_reward_df))
                # Duplicate column and apply
                # URL formatting to one of the columns.
                survey_reward_df["basis_function_href"] = survey_reward_df.loc[:, "basis_function"]
                survey_reward_df["basis_function_href"] = survey_reward_df.apply(
                    url_formatter,
                    axis=1,
                    args=("basis_function_href", "doc_url"),
                )
                self._survey_reward_df = survey_reward_df
                self._debugging_message = "Finished making reward dataframe."
            else:
                self._survey_reward_df = None
                self._debugging_message = "No reward dataframe made; survey has no rewards."

        except Exception:
            tb = traceback.format_exc(limit=-1)
            self._debugging_message = f"Cannot make survey reward dataframe: \n{tb}"
            pn.state.notifications.error("Cannot make survey reward dataframe!", duration=0)

    def create_reward_widget(self):
        """Create Tabulator widget with survey reward dataframe."""
        if self._survey_reward_df is None:
            return

        self._debugging_message = "Starting to create reward widget."
        tabulator_formatter = {
            "basis_function_href": HTMLTemplateFormatter(template="<%= value %>"),
            "feasible": BooleanFormatter(),
            "basis_area": NumberFormatter(format="0.00"),
            "accum_area": NumberFormatter(format="0.00"),
            "max_basis_reward": NumberFormatter(format="0.000"),
            "max_accum_reward": NumberFormatter(format="0.000"),
            "basis_weight": NumberFormatter(format="0.0"),
        }
        columns = [
            "basis_function",
            "basis_function_href",
            "feasible",
            "max_basis_reward",
            "basis_area",
            "basis_weight",
            "accum_order",
            "max_accum_reward",
            "accum_area",
            "doc_url",
        ]
        titles = {
            "basis_function": "Basis Function",
            "basis_function_href": "Docs",
            "feasible": "Feasible",
            "max_basis_reward": "Max. Reward",
            "basis_area": "Area (deg<sup>2</sup>)",
            "basis_weight": "Weight",
            "accum_order": "Accum. Order",
            "max_accum_reward": "Max. Accum. Reward",
            "accum_area": "Accum. Area (deg<sup>2</sup>)",
        }
        text_align = {
            "basis_function": "left",
            "basis_function_href": "center",
            "feasible": "center",
            "max_basis_reward": "right",
            "basis_area": "right",
            "basis_weight": "right",
            "accum_order": "right",
            "max_accum_reward": "right",
            "accum_area": "right",
        }
        sortable = {
            "feasible": False,
            "basis_function_href": False,
        }
        widths = {
            "basis_function": "14%",
            "basis_function_href": "5%",
            "feasible": "6%",
            "max_basis_reward": "10%",
            "basis_area": "12%",
            "basis_weight": "8%",
            "accum_order": "13%",
            "max_accum_reward": "15%",
            "accum_area": "15%",
        }

        reward_widget = pn.widgets.Tabulator(
            self._survey_reward_df[columns],
            titles=titles,
            text_align=text_align,
            sortable=sortable,
            show_index=False,
            formatters=tabulator_formatter,
            disabled=True,
            frozen_columns=["basis_function"],
            hidden_columns=["doc_url"],
            selectable=1,
            height=self._reward_widget_height,
            widths=widths,
        )
        self.reward_widget = reward_widget
        self._debugging_message = "Finished making reward widget."

    def update_reward_widget_data(self):
        """Update survey reward Tabulator widget data."""
        if self._survey_reward_df is None:
            return

        self._debugging_message = "Starting to update reward widget data."
        self.reward_widget.selection = []
        columns = [
            "basis_function",
            "basis_function_href",
            "feasible",
            "max_basis_reward",
            "basis_area",
            "basis_weight",
            "accum_order",
            "max_accum_reward",
            "accum_area",
            "doc_url",
        ]
        self.reward_widget._update_data(self._survey_reward_df[columns])
        self._debugging_message = "Finished updating reward widget data."

    @param.depends("_publish_reward_widget")
    def publish_reward_widget(self):
        """Return the reward Tabulator widget for display.

        Returns
        -------
        widget: `panel.widgets.Tabulator`
            Table of reward data for selected survey.
        """
        if self._survey_reward_df is None:
            return "No rewards available."
        else:
            self._debugging_message = "Publishing reward widget."
            return self.reward_widget

    def create_sky_map_base(self):
        """Create a base plot with a dummy map."""
        if self._survey_maps is None:
            self._debugging_message = "Cannot create sky map as no survey maps made."
            return

        try:
            self._debugging_message = "Starting to create sky map base."
            # Make a dummy map that is 1.0 for all healpixels
            # that might have data.
            self._survey_maps["above_horizon"] = np.where(self._conditions.alt > 0, 1.0, np.nan)
            self._sky_map_base = schedview.plot.survey.map_survey_healpix(
                self._conditions.mjd,
                self._survey_maps,
                "above_horizon",
                np.int64(self.nside),
                conditions=self._conditions,
                survey=self._scheduler.survey_lists[int(self._tier[-1])][self._survey],
            )
            self._sky_map_base.plot.toolbar.tools[-1].tooltips.remove(("above_horizon", "@above_horizon"))

            color_bar = ColorBar(
                color_mapper=LinearColorMapper(palette=self.color_palette, low=0, high=1),
                label_standoff=10,
                location=(0, 0),
            )
            self._sky_map_base.plot.add_layout(color_bar, "below")
            self._sky_map_base.plot.below[1].visible = False
            self._sky_map_base.plot.toolbar.autohide = True  # Show toolbar only when mouseover plot.
            self._sky_map_base.plot.title.text = ""  # Remove 'Horizon' title.
            self._sky_map_base.plot.legend.propagate_hover = True  # Hover tool works over in-plot legend.
            self._sky_map_base.plot.legend.title = "Key"
            self._sky_map_base.plot.legend.title_text_font_style = "bold"
            self._sky_map_base.plot.legend.border_line_color = "#048b8c"
            self._sky_map_base.plot.legend.border_line_width = 3
            self._sky_map_base.plot.legend.border_line_alpha = 1
            self._sky_map_base.plot.legend.label_standoff = 10  # Gap between images and text.
            self._sky_map_base.plot.legend.padding = 15  # Space around inside edge.
            self._sky_map_base.plot.legend.title_standoff = 10  # Space between title and items.
            self._sky_map_base.plot.legend.click_policy = "hide"  # Hide elements when clicked.
            moved_legend = self._sky_map_base.plot.legend[0].clone()
            self._sky_map_base.plot.legend[0].destroy()
            self._sky_map_base.plot.add_layout(moved_legend, "right")
            self._sky_map_base.plot.right[0].location = "center_right"

            self._debugging_message = "Finished creating sky map base."

        except Exception:
            self._debugging_message = f"Cannot create sky map base: \n{traceback.format_exc(limit=-1)}"
            pn.state.notifications.error("Cannot create sky map base!", duration=0)

    def update_sky_map_with_survey_map(self):
        """Update base plot with healpixel data from selected survey map.

        Notes
        -----
        There are three possible update cases:
         - Case 1: Selection is a reward map.
         - Case 2: Selection is a survey map and is all NaNs.
         - Case 3: Selection is a survey map and is not all NaNs.
        """
        if self._sky_map_base is None:
            self._debugging_message = "Cannot update sky map with survey map as no base map loaded."
            return

        try:
            self._debugging_message = "Starting to update sky map with survey map."
            hpix_renderer = self._sky_map_base.plot.select(name="hpix_renderer")[0]
            hpix_data_source = self._sky_map_base.plot.select(name="hpix_ds")[0]

            # CASE 1: Selection is a reward map.
            if self.survey_map not in ["u_sky", "g_sky", "r_sky", "i_sky", "z_sky", "y_sky", "reward"]:
                reward_underscored = self._map_name.replace(" ", "_")
                reward_survey_key = list(key for key in self._survey_maps if self._map_name in key)[0]
                reward_bokeh_key = list(key for key in hpix_data_source.data if reward_underscored in key)[0]

                min_good_value = np.nanmin(self._survey_maps[reward_survey_key])
                max_good_value = np.nanmax(self._survey_maps[reward_survey_key])

                if min_good_value == max_good_value:
                    min_good_value -= 1
                    max_good_value += 1

                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=reward_bokeh_key,
                    palette=self.color_palette,
                    low=min_good_value,
                    high=max_good_value,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = True
                self._sky_map_base.plot.below[1].color_mapper.palette = self.color_palette
                self._sky_map_base.plot.below[1].color_mapper.low = min_good_value
                self._sky_map_base.plot.below[1].color_mapper.high = max_good_value

            # CASE 2: Selection is a survey map and is all NaNs.
            elif np.isnan(self._survey_maps[self.survey_map]).all():
                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=self.survey_map,
                    palette=self.color_palette,
                    low=-1,
                    high=1,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = False

            # CASE 3: Selection is a survey map and is not all NaNs.
            else:
                min_good_value = np.nanmin(self._survey_maps[self.survey_map])
                max_good_value = np.nanmax(self._survey_maps[self.survey_map])

                if min_good_value == max_good_value:
                    min_good_value -= 1
                    max_good_value += 1

                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=self.survey_map,
                    palette=self.color_palette,
                    low=min_good_value,
                    high=max_good_value,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = True
                self._sky_map_base.plot.below[1].color_mapper.palette = self.color_palette
                self._sky_map_base.plot.below[1].color_mapper.low = min_good_value
                self._sky_map_base.plot.below[1].color_mapper.high = max_good_value
            hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
            self._sky_map_base.update()
            self._debugging_message = "Finished updating sky map with survey map."

        except Exception:
            self._debugging_message = f"Cannot update sky map: \n{traceback.format_exc(limit=-1)}"
            pn.state.notifications.error("Cannot update sky map!", duration=0)

    def update_sky_map_with_reward(self):
        """Update base plot with healpixel data from selected survey map.

        Notes
        -----
        There are three possible update cases:
         - Case 1: Reward is not scalar.
         - Case 2: Reward is scalar and finite.
         - Case 3: Reward is -Inf.
        """
        if self._sky_map_base is None:
            self._debugging_message = "Cannot update sky map with reward as no base map is loaded."
            return

        try:
            self._debugging_message = "Starting to update sky map with reward."
            hpix_renderer = self._sky_map_base.plot.select(name="hpix_renderer")[0]
            hpix_data_source = self._sky_map_base.plot.select(name="hpix_ds")[0]

            reward_underscored = self._reward_name.replace(" ", "_")
            max_basis_reward = self._survey_reward_df.loc[self._reward, :]["max_basis_reward"]

            # CASE 1: Reward is not scalar.
            if any(self._reward_name in key for key in self._survey_maps):
                reward_survey_key = list(key for key in self._survey_maps if self._reward_name in key)[0]
                reward_bokeh_key = list(key for key in hpix_data_source.data if reward_underscored in key)[0]

                min_good_value = np.nanmin(self._survey_maps[reward_survey_key])
                max_good_value = np.nanmax(self._survey_maps[reward_survey_key])

                if min_good_value == max_good_value:
                    min_good_value -= 1
                    max_good_value += 1

                # Modify existing bokeh object.
                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=reward_bokeh_key,
                    palette=self.color_palette,
                    low=min_good_value,
                    high=max_good_value,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = True
                self._sky_map_base.plot.below[1].color_mapper.palette = self.color_palette
                self._sky_map_base.plot.below[1].color_mapper.low = min_good_value
                self._sky_map_base.plot.below[1].color_mapper.high = max_good_value

            # CASE 2: Reward is scalar and finite.
            elif max_basis_reward != -np.inf:
                # Create array populated with scalar values
                # where sky brightness map is not NaN.
                scalar_array = hpix_data_source.data["u_sky"].copy()
                scalar_array[~np.isnan(hpix_data_source.data["u_sky"])] = max_basis_reward
                hpix_data_source.data[reward_underscored] = scalar_array

                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=reward_underscored,
                    palette=self.color_palette,
                    low=max_basis_reward - 1,
                    high=max_basis_reward + 1,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = True
                self._sky_map_base.plot.below[1].color_mapper.palette = self.color_palette
                self._sky_map_base.plot.below[1].color_mapper.low = max_basis_reward - 1
                self._sky_map_base.plot.below[1].color_mapper.high = max_basis_reward + 1

            # CASE 3: Reward is -Inf.
            else:
                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=self._reward_name,
                    palette="Greys256",
                    low=-1,
                    high=1,
                    nan_color="white",
                )
                self._sky_map_base.plot.below[1].visible = False
            hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
            self._sky_map_base.update()
            self._debugging_message = "Finished updating sky map with reward."

        except Exception:
            self._debugging_message = f"Cannot update sky map: \n{traceback.format_exc(limit=-1)}"
            pn.state.notifications.error("Cannot update sky map!", duration=0)

    @param.depends("_publish_map")
    def publish_sky_map(self):
        """Return the Bokeh plot for display.

        Returns
        -------
        sky_map : `bokeh.models.layouts.Column`
            Map of survey map or reward map as a Bokeh plot.
        """
        if self._conditions is None:
            return "No scheduler loaded."

        elif self._survey_maps is None:
            return "No surveys are loaded."

        elif self._sky_map_base is None:
            return "No map loaded."

        else:
            self._debugging_message = "Publishing sky map."
            return self._sky_map_base.figure

    @param.depends("_debugging_message")
    def _debugging_messages(self):
        """Construct a debugging pane to display error messages.

        Returns
        -------
        debugging_messages : `panel.pane.Str`
            A list of debugging messages ordered by newest message first.
        """
        if self._debugging_message is None:
            return None

        timestamp = datetime.now(timezone("America/Santiago")).strftime("%Y-%m-%d %H:%M:%S")
        self._debug_string = f"\n {timestamp} - {self._debugging_message}" + self._debug_string

        # Send messages to stderr.
        self.logger.debug(self._debugging_message)

        if self.debug_pane is None:
            self.debug_pane = pn.pane.Str(
                self._debug_string,
                height=200,
                styles={
                    "font-size": "9pt",
                    "color": "black",
                    "overflow": "scroll",
                    "background": "#EDEDED",
                },
            )
        else:
            self.debug_pane.object = self._debug_string
        return self.debug_pane

    # ----------------------------------------------------- Dashboard titles.
    # The following set of functions are responsible for
    # generating and updating the various text headings
    # throughout the dashboard.

    def generate_dashboard_subtitle(self):
        """Select the dashboard subtitle string based on whether a
        survey map or reward map is being displayed.

        Returns
        -------
        subtitle : `str`
            Heading text. Include tier and survey, and either the
            survey or reward map.
        """
        if not self._display_dashboard_data:
            return ""
        maps = ["u_sky", "g_sky", "r_sky", "i_sky", "z_sky", "y_sky", "reward"]
        if not self._display_reward and self.survey_map in maps:
            return f"\nTier {self._tier[-1]} - Survey {self._survey} - Map {self._map_name}"
        elif not self._display_reward and self.survey_map not in maps:
            return f"\nTier {self._tier[-1]} - Survey {self._survey} - Reward {self._map_name}"
        else:
            return f"\nTier {self._tier[-1]} - Survey {self._survey} - Reward {self._reward_name}"

    def generate_chosen_survey_label(self):
        """Generate a string listing the chosen survey.

        Returns
        -------
        label : `str`
            Label text. Include tier and survey.
        """
        if not self._display_dashboard_data:
            return "Chosen survey is ..."
        self._scheduler.request_observation()
        if self._scheduler.survey_index[0] is None or self._scheduler.survey_index[1] is None:
            return "No survey chosen."

        label = (
            self._reward_df.loc[tuple(self._scheduler.survey_index), ("tier_label", "survey_label")]
            .drop_duplicates()
            .values
        )
        tier_label = label[0][0]
        survey_label = label[0][1]
        return f"Chosen survey is {tier_label}, {survey_label}."

    def generate_summary_table_heading(self):
        """Select the summary table heading based on whether data is being
        displayed or not.

        Returns
        -------
        heading : `str`
            Heading text. If data is diplayed, include current tier;
            else, a general heading.
        """
        if not self._display_dashboard_data:
            return "Scheduler summary"
        else:
            return f"Scheduler summary for tier {self._tier[-1]}"

    def generate_reward_table_heading(self):
        """Select the reward table heading based on whether data is
        being displayed or not.

        Returns
        -------
        heading : `str`
            Heading text. If data is diplayed, include current survey;
            else, a general heading.
        """
        if not self._display_dashboard_data:
            return "Basis functions & rewards"
        else:
            return f"Basis functions & rewards for survey {self._survey_name}"

    def generate_map_heading(self):
        """Select the map heading based on whether a survey or reward map
        is being displayed.

        Returns
        -------
        heading : `str`
            Heading text. If data is displayed, include current survey and
            either the survey map or reward name; else, a general heading.
        """
        if not self._display_dashboard_data:
            return "Map"
        maps = ["u_sky", "g_sky", "r_sky", "i_sky", "z_sky", "y_sky", "reward"]
        if not self._display_reward and self.survey_map in maps:
            return f"Survey {self._survey_name}\nMap: {self._map_name}"
        elif not self._display_reward and self.survey_map not in maps:
            return f"Survey {self._survey_name}\nReward: {self._map_name}"
        else:
            return f"Survey {self._survey_name}\nReward: {self._reward_name}"

    @param.depends("_update_headings")
    def dashboard_subtitle(self):
        """Load subtitle data and create/update
        a String pane to display subtitle.

        Returns
        -------
        title : `panel.pane.Str`
            A panel String pane to display as the dashboard's subtitle.
        """
        title_string = self.generate_dashboard_subtitle()
        if self.dashboard_subtitle_pane is None:
            self.dashboard_subtitle_pane = pn.pane.Str(
                title_string,
                height=20,
                stylesheets=[h2_stylesheet],
            )
        else:
            self.dashboard_subtitle_pane.object = title_string
        return self.dashboard_subtitle_pane

    @param.depends("_update_chosen_survey")
    def chosen_survey_label(self):
        """Load label data and create/update
        a String pane to display label.

        Returns
        -------
        label : `panel.pane.Str`
            A panel String pane to display the chosen survey label.
        """
        chosen_survey_string = self.generate_chosen_survey_label()
        if self.chosen_survey_label_pane is None:
            self.chosen_survey_label_pane = pn.pane.Str(
                chosen_survey_string,
                stylesheets=[h3_stylesheet],
            )
        else:
            self.chosen_survey_label_pane.object = chosen_survey_string
        return self.chosen_survey_label_pane

    @param.depends("_update_headings")
    def summary_table_heading(self):
        """Load heading data and create/update
        a String pane to display heading.

        Returns
        -------
        title : `panel.pane.Str`
            A panel String pane to display as the survey table's heading.
        """
        title_string = self.generate_summary_table_heading()
        if self.summary_table_heading_pane is None:
            self.summary_table_heading_pane = pn.pane.Str(
                title_string,
                stylesheets=[h3_stylesheet],
            )
        else:
            self.summary_table_heading_pane.object = title_string
        return self.summary_table_heading_pane

    @param.depends("_update_headings")
    def reward_table_heading(self):
        """Load title data and create/update a String pane to display heading.

        Returns
        -------
        title : `panel.pane.Str`
            A panel String pane to display as the reward table heading.
        """
        title_string = self.generate_reward_table_heading()
        if self.reward_table_heading_pane is None:
            self.reward_table_heading_pane = pn.pane.Str(
                title_string,
                stylesheets=[h3_stylesheet],
            )
        else:
            self.reward_table_heading_pane.object = title_string
        return self.reward_table_heading_pane

    @param.depends("_update_headings")
    def map_title(self):
        """Load title data and create/update a String pane to display heading.

        Returns
        -------
        title : `panel.pane.Str`
            A panel String pane to display as the map heading.
        """
        title_string = self.generate_map_heading()
        if self.map_title_pane is None:
            self.map_title_pane = pn.pane.Str(
                title_string,
                stylesheets=[h3_stylesheet],
            )
        else:
            self.map_title_pane.object = title_string
        return self.map_title_pane
