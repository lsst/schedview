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

import importlib.resources
import logging
import os
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import bokeh
import numpy as np
import panel as pn
import param
from astropy.time import Time
from bokeh.models import ColorBar, LinearColorMapper
from bokeh.models.widgets.tables import BooleanFormatter, HTMLTemplateFormatter
from pandas import Timestamp
from pytz import timezone

# For the conditions.mjd bugfix
from rubin_sim.scheduler.model_observatory import ModelObservatory

import schedview
import schedview.collect.scheduler_pickle
import schedview.compute.scheduler
import schedview.compute.survey
import schedview.plot.survey

DEFAULT_CURRENT_TIME = Time.now()
DEFAULT_TIMEZONE = "America/Santiago"
COLOR_PALETTES = [color for color in bokeh.palettes.__palettes__ if "256" in color]
LOGO = "/assets/lsst_white_logo.png"

pn.extension(
    "tabulator",
    sizing_mode="stretch_width",
    notifications=True,
)

logging.basicConfig(
    format="%(asctime)s %(message)s",
    level=logging.INFO,
)

# Change styles using CSS variables.
stylesheet = """
:host {
--mono-font: Helvetica;
}
"""


def url_formatter(dataframe_row, name_column, url_column):
    """Format survey name as a HTML href to survey URL (if URL exists).

    Parameters
    ----------
    dataframe_row : 'pandas.core.series.Series'
        A row of a pandas.core.frame.DataFrame.

    Returns
    -------
    survey_name_or_url : 'str'
        A HTML href or plain string.
    """
    if dataframe_row[url_column] == "":
        return dataframe_row[name_column]
    else:
        return f'<a href="{dataframe_row[url_column]}" target="_blank"> {dataframe_row[name_column]}</a>'


class Scheduler(param.Parameterized):
    """A Parametrized container for parameters, data, and panel objects for the
    scheduler dashboard.
    """

    # Param parameters that are modifiable by user actions.
    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
    Such a pickle file can either be of an instance of a subclass of
    rubin_sim.scheduler.schedulers.CoreScheduler, or a tuple of the form
    (scheduler, conditions), where scheduler is an instance of a subclass of
    rubin_sim.scheduler.schedulers.CoreScheduler, and conditions is an
    instance of rubin_sim.scheduler.conditions.Conditions.
    """
    scheduler_fname = param.String(
        default="",
        label="Scheduler pickle file",
        doc=scheduler_fname_doc,
    )
    date = param.Date(default=DEFAULT_CURRENT_TIME.datetime.date(), doc="")
    USER_tier = param.Selector(
        default="",
        objects=[""],
        label="Tier",
        doc="The label for the first index into the CoreScheduler.survey_lists.",
    )
    survey_map = param.Selector(
        default="reward",
        objects=["reward"],
        doc="Sky brightness maps, non-scalar rewards and survey reward map.",
    )
    nside = param.ObjectSelector(
        default=16,
        objects=[2**n for n in np.arange(1, 6)],
        label="Map resolution (nside)",
        doc="",
    )
    color_palette = param.Selector(default="Viridis256", objects=COLOR_PALETTES, doc="")
    summary_widget = param.Parameter(default=None, doc="")
    reward_widget = param.Parameter(default=None, doc="")

    # Param parameters (used in depends decoraters and trigger calls).
    _publish_summary_widget = param.Parameter(None)
    _publish_reward_widget = param.Parameter(None)
    _publish_map = param.Parameter(None)
    _update_headings = param.Parameter(None)
    _debugging_message = param.Parameter(None)

    # Non-Param parameters storing Panel pane objects.
    debug_pane = None
    dashboard_subtitle_pane = None
    summary_table_heading_pane = None
    reward_table_heading_pane = None
    map_title_pane = None

    # Non-Param internal parameters.
    _tier = None
    _survey = 0
    _reward = -1
    _survey_name = ""
    _reward_name = ""
    _map_name = ""
    _scheduler = None
    _conditions = None
    _date_time = None
    _reward_df = None
    _scheduler_summary_df = None
    _survey_maps = None
    _survey_reward_df = None
    _sky_map_base = None
    _debug_string = ""
    _display_reward = False
    _display_dashboard_data = False
    _do_not_trigger_update = True
    _show_loading_indicator = False
    _model_observatory = ModelObservatory(init_load_length=1)

    # ------------------------------------------------- User actions

    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler_fname(self):
        """Update the dashboard when a user enters a new filepath/URL."""
        self._show_loading_indicator = True
        self.clear_dashboard()

        if not self.read_scheduler():
            self.clear_dashboard()
            self._show_loading_indicator = False
            return

        if not self.make_scheduler_summary_df():
            self.clear_dashboard()
            self._show_loading_indicator = False
            return

        self.create_summary_widget()
        self.param.trigger("_publish_summary_widget")

        self._do_not_trigger_update = True
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

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

        self._show_loading_indicator = False

    @param.depends("date", watch=True)
    def _update_date(self):
        """Update the dashboard when a user chooses a new date/time."""
        self._show_loading_indicator = True
        self.clear_dashboard()

        self._date_time = Time(
            Timestamp(
                self.date,
                tzinfo=ZoneInfo(DEFAULT_TIMEZONE),
            )
        ).mjd

        if not self.make_scheduler_summary_df():
            self.clear_dashboard()
            self._show_loading_indicator = False
            return

        if self.summary_widget is None:
            self.create_summary_widget()
        else:
            self.update_summary_widget_data()
        self.param.trigger("_publish_summary_widget")

        self._do_not_trigger_update = True
        self.summary_widget.selection = [0]
        self._do_not_trigger_update = False

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

        self._show_loading_indicator = False

    @param.depends("USER_tier", watch=True)
    def _update_tier(self):
        """Update the dashboard when a user chooses a new tier."""
        if not self._display_dashboard_data:
            return

        self._tier = self.USER_tier
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

        self.compute_survey_maps()

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

    @param.depends("color_palette", watch=True)
    def _update_color_palette(self):
        """Update the dashboard when a user chooses a new color palette."""
        if self._display_reward:
            self.update_sky_map_with_reward()
        else:
            self.update_sky_map_with_survey_map()
        self.param.trigger("_publish_map")

    # ------------------------------------------------------ Internal workings

    def clear_dashboard(self):
        """Clear the dashboard for a new pickle or a new date."""
        self._debugging_message = "Starting to clear dashboard."

        self.summary_widget = None
        self._survey_reward_df = None
        self._sky_map_base = None
        self._display_dashboard_data = False

        self.param.trigger("_publish_summary_widget")
        self.param.trigger("_publish_reward_widget")
        self.param.trigger("_publish_map")
        self.param.trigger("_update_headings")

        self.param["USER_tier"].objects = [""]
        self.param["survey_map"].objects = [""]

        self.USER_tier = ""
        self.survey_map = ""

        self._tier = ""
        self._survey = 0
        self._reward = -1

        self._debugging_message = "Finished clearing dashboard."

    def read_scheduler(self):
        """Load the scheduler and conditions objects from pickle file.

        Returns
        -------
        success : 'bool'
            Record of success or failure of reading scheduler from file/URL.
        """
        try:
            self._debugging_message = "Starting to load scheduler."
            pn.state.notifications.info("Scheduler loading...", duration=0)

            (scheduler, conditions) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)
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

    def make_scheduler_summary_df(self):
        """Update conditions, make the reward and scheduler summary dataframes.

        Returns
        -------
        success : 'bool'
            Record of success of conditions update and dataframe construction.
        """
        if self._scheduler is None:
            self._debugging_message = "Cannot update survey reward table as no pickle is loaded."

            return False

        try:
            self._debugging_message = "Starting to make scheduler summary dataframe."
            pn.state.notifications.info("Making scheduler summary dataframe...", duration=0)

            # TODO: Conditions setter bug-fix.

            # self._conditions.mjd = self._date_time
            if self._model_observatory.nside != self._scheduler.nside:
                self._model_observatory = ModelObservatory(
                    nside=self._scheduler.nside,
                    init_load_length=1,
                )
            self._model_observatory.mjd = self._date_time
            self._conditions = self._model_observatory.return_conditions()

            self._scheduler.update_conditions(self._conditions)
            self._reward_df = self._scheduler.make_reward_df(self._conditions)
            scheduler_summary_df = schedview.compute.scheduler.make_scheduler_summary_df(
                self._scheduler,
                self._conditions,
                self._reward_df,
            )

            # Duplicate column and apply URL formatting to one of the columns.
            scheduler_summary_df["survey"] = scheduler_summary_df.loc[:, "survey_name"]
            scheduler_summary_df["survey_name"] = scheduler_summary_df.apply(
                url_formatter,
                axis=1,
                args=("survey_name", "survey_url"),
            )
            self._scheduler_summary_df = scheduler_summary_df

            tiers = self._scheduler_summary_df.tier.unique().tolist()
            self.param["USER_tier"].objects = tiers
            self.USER_tier = tiers[0]
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
        tabulator_formatter = {"survey_name": HTMLTemplateFormatter(template="<%= value %>")}
        columns = [
            "tier",
            "survey_name",
            "reward",
            "survey",
            "survey_url",
        ]
        titles = {
            "survey_name": "Survey",
            "reward": "Reward",
        }
        summary_widget = pn.widgets.Tabulator(
            self._scheduler_summary_df[self._scheduler_summary_df["tier"] == self._tier][columns],
            widths={"survey_name": "60%", "reward": "40%"},
            show_index=False,
            formatters=tabulator_formatter,
            titles=titles,
            disabled=True,
            selectable=1,
            hidden_columns=["tier", "survey", "survey_url"],
            pagination="remote",
            page_size=4,
            sizing_mode="stretch_width",
        )
        self.summary_widget = summary_widget
        self._debugging_message = "Finished making summary widget."

    def update_summary_widget_data(self):
        """Update data for survey Tabulator widget."""
        self._debugging_message = "Starting to update summary widget."
        columns = [
            "tier",
            "survey_name",
            "reward",
            "survey",
            "survey_url",
        ]
        self.summary_widget._update_data(
            self._scheduler_summary_df[self._scheduler_summary_df["tier"] == self._tier][columns]
        )
        self._debugging_message = "Finished updating summary widget."

    @param.depends("_publish_summary_widget")
    def publish_summary_widget(self):
        """Publish the summary Tabulator widget to be shown on the dashboard.

        Returns
        -------
        widget: 'panel.widgets.Tabulator'
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
                self.nside,
            )
            self.param["survey_map"].objects = [""] + list(self._survey_maps.keys())
            self._debugging_message = "Finished computing survey maps."

        except Exception:
            self._debugging_message = f"Cannot compute survey maps: \n{traceback.format_exc(limit=-1)}"
            pn.state.notifications.error("Cannot compute survey maps!", duration=0)

    def make_reward_df(self):
        """Make the summary dataframe."""
        if self._scheduler is None:
            self._debugging_message = "Cannot make summary dataframe as no scheduler loaded."
            return
        if self._scheduler_summary_df is None:
            self._debugging_message = "Cannot make summary dataframe as no scheduler summary made."
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
                # Duplicate column and apply URL formatting
                # to one of the columns.
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
        }
        columns = [
            "basis_function_href",
            "basis_function_class",
            "feasible",
            "max_basis_reward",
            "basis_area",
            "basis_weight",
            "max_accum_reward",
            "accum_area",
            "doc_url",
            "basis_function",
        ]
        titles = {
            "basis_function_href": "Basis Function",
            "basis_function_class": "Class",
            "feasible": "Feasible",
            "max_basis_reward": "Max Reward",
            "basis_area": "Area",
            "basis_weight": "Weight",
            "max_accum_reward": "Max Accumulated Reward",
            "accum_area": "Accumulated Area",
        }
        reward_widget = pn.widgets.Tabulator(
            self._survey_reward_df[columns],
            titles=titles,
            layout="fit_data",
            show_index=False,
            formatters=tabulator_formatter,
            disabled=True,
            frozen_columns=["basis_function_href"],
            hidden_columns=["basis_function", "doc_url"],
            selectable=1,
            pagination="remote",
            page_size=13,
        )
        self.reward_widget = reward_widget
        self._debugging_message = "Finished making reward widget."

    def update_reward_widget_data(self):
        """Update Treward abulator widget data."""
        if self._survey_reward_df is None:
            return

        self._debugging_message = "Starting to update reward widget data."
        self.reward_widget.selection = []
        columns = [
            "basis_function_href",
            "basis_function_class",
            "feasible",
            "max_basis_reward",
            "basis_area",
            "basis_weight",
            "max_accum_reward",
            "accum_area",
            "doc_url",
            "basis_function",
        ]
        self.reward_widget._update_data(self._survey_reward_df[columns])
        self._debugging_message = "Finished updating reward widget data."

    @param.depends("_publish_reward_widget")
    def publish_reward_widget(self):
        """Return the reward Tabulator widget for display.

        Returns
        -------
        widget: 'panel.widgets.Tabulator'
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
                self.nside,
            )
            self._sky_map_base.plot.toolbar.tools[-1].tooltips.remove(("above_horizon", "@above_horizon"))

            color_bar = ColorBar(
                color_mapper=LinearColorMapper(palette=self.color_palette, low=0, high=1),
                label_standoff=10,
                location=(0, 0),
            )
            self._sky_map_base.plot.add_layout(color_bar, "below")
            self._sky_map_base.plot.below[1].visible = False
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
            if self.survey_map not in [
                "u_sky",
                "g_sky",
                "r_sky",
                "i_sky",
                "z_sky",
                "y_sky",
                "reward",
            ]:
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
                # Create array populated with scalar values where
                # the sky brightness map is not NaN.
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
        sky_map : 'bokeh.models.layouts.Column'
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
        debugging_messages : 'panel.pane.Str'
            A list of debugging messages ordered by newest message first.
        """
        if self._debugging_message is None:
            return None

        timestamp = datetime.now(timezone("America/Santiago")).strftime("%Y-%m-%d %H:%M:%S")
        self._debug_string = f"\n {timestamp} - {self._debugging_message}" + self._debug_string

        if self.debug_pane is None:
            self.debug_pane = pn.pane.Str(
                self._debug_string,
                height=200,
                styles={"font-size": "9pt", "color": "black", "overflow": "scroll"},
            )
        else:
            self.debug_pane.object = self._debug_string
        return self.debug_pane

    @param.depends("_show_loading_indicator", watch=True)
    def update_loading_indicator(self):
        """Update the app to show or stop showing the loading indicator."""
        sched_app.loading = self._show_loading_indicator

    # ------------------------------------------------------- Dashboard titles

    def generate_dashboard_subtitle(self):
        """Select the dashboard subtitle string based on whether whether a
        survey map or reward map is being displayed.

        Returns
        -------
        subtitle : 'str'
            Lists the tier and survey, and either the survey or reward map.
        """
        if not self._display_dashboard_data:
            return ""
        maps = ["u_sky", "g_sky", "r_sky", "i_sky", "z_sky", "y_sky", "reward"]
        survey = self._survey_name.split(":")[0]
        if not self._display_reward and self.survey_map in maps:
            return f"\nTier {self._tier[-1]} - Survey {survey} - Map {self._map_name}"
        elif not self._display_reward and self.survey_map not in maps:
            return f"\nTier {self._tier[-1]} - Survey {survey} - Reward {self._map_name}"
        else:
            return f"\nTier {self._tier[-1]} - Survey {survey} - Reward {self._reward_name}"

    def generate_summary_table_heading(self):
        """Select the summary table heading based on whether data is being
        displayed or not.

        Returns
        -------
        heading : 'str'
            Lists the tier if data is displayed; else just a general title.
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
        heading : 'str'
            Lists the survey name if data is displayed; else a general title.
        """
        if not self._display_dashboard_data:
            return "Rewards"
        else:
            return f"Rewards for survey {self._survey_name}"

    def generate_map_heading(self):
        """Select the map heading based on whether a survey or reward map
        is being displayed.

        Returns
        -------
        heading : 'str'
            Lists the survey name and either the survey map name or reward
            name if data is being displayed; else a general title.
        """
        if not self._display_dashboard_data:
            return "Map"
        maps = ["u_sky", "g_sky", "r_sky", "i_sky", "z_sky", "y_sky", "reward"]
        if not self._display_reward and self.survey_map in maps:
            return f"Survey {self._survey_name}\nMap: {self._map_name}"
        elif not self._display_reward and self.survey_map not in maps:
            return f"Survey {self._survey_name}\nReward: {self._map_name}"
        else:
            return f"Survey {self._survey_name}\nReward {self._reward_name}"

    @param.depends("_update_headings")
    def dashboard_subtitle(self):
        """Load subtitle data and create/update a pane to display subtitle.

        Returns
        -------
        title : 'panel.pane.Str'
            A panel String pane to display as the dashboard's subtitle.
        """
        title_string = self.generate_dashboard_subtitle()
        if self.dashboard_subtitle_pane is None:
            self.dashboard_subtitle_pane = pn.pane.Str(
                title_string,
                height=20,
                styles={"font-size": "14pt", "font-weight": "300", "color": "white"},
                stylesheets=[stylesheet],
            )
        else:
            self.dashboard_subtitle_pane.object = title_string
        return self.dashboard_subtitle_pane

    @param.depends("_update_headings")
    def summary_table_heading(self):
        """Load heading data and create/update a pane to display heading.

        Returns
        -------
        title : 'panel.pane.Str'
            A panel String pane to display as the survey table's heading.
        """
        title_string = self.generate_summary_table_heading()
        if self.summary_table_heading_pane is None:
            self.summary_table_heading_pane = pn.pane.Str(
                title_string,
                styles={"font-size": "13pt", "font-weight": "300", "color": "white"},
                stylesheets=[stylesheet],
            )
        else:
            self.summary_table_heading_pane.object = title_string
        return self.summary_table_heading_pane

    @param.depends("_update_headings")
    def reward_table_heading(self):
        """Load title data and create/update a String pane to display heading.

        Returns
        -------
        title : 'panel.pane.Str'
            A panel String pane to display as the reward table heading.
        """
        title_string = self.generate_reward_table_heading()
        if self.reward_table_heading_pane is None:
            self.reward_table_heading_pane = pn.pane.Str(
                title_string,
                styles={"font-size": "13pt", "font-weight": "300", "color": "white"},
                stylesheets=[stylesheet],
                css_classes=["title"],
            )
        else:
            self.reward_table_heading_pane.object = title_string
        return self.reward_table_heading_pane

    @param.depends("_update_headings")
    def map_title(self):
        """Load title data and create/update a String pane to display heading.

        Returns
        -------
        title : 'panel.pane.Str'
            A panel String pane to display as the map heading.
        """
        title_string = self.generate_map_heading()
        if self.map_title_pane is None:
            self.map_title_pane = pn.pane.Str(
                title_string,
                styles={"font-size": "13pt", "font-weight": "300", "color": "white"},
                stylesheets=[stylesheet],
            )
        else:
            self.map_title_pane.object = title_string
        return self.map_title_pane


# -------------------------------------------------------------- Key functions


def generate_array_for_key(number_of_columns=4):
    """Create a dictionary of data for the key.

    Parameters
    ----------
    number_of_columns : 'int', optional
        The number of columns to display key objects in. The default is 4.

    Returns
    -------
    data : 'dict'
        Coordinate, styling and text data for key.
    """
    return {
        # x,y coordinates for glyphs (lines, circles and text).
        "x_title": np.array([7]),  # Title x coord
        "y_title": np.array([5.75]),  # Title y coord
        "x_circles": np.tile(8, number_of_columns),  # Circle centre coords
        "x_text_1": np.tile(2.5, number_of_columns),  # Text in colunn 1
        "x_text_2": np.tile(8.75, number_of_columns),  # Text in column 2
        "x0_lines": np.tile(0.75, number_of_columns),  # Start lines
        "x1_lines": np.tile(2, number_of_columns),  # End lines
        "y": np.arange(number_of_columns, 0, -1),  # y coords for all items except title
        # Colours and sizes of images.
        "line_colours": np.array(["black", "red", "#1f8f20", "#110cff"]),
        "circle_colours": np.array(["#ffa500", "brown", "red", "#1f8f20"]),
        "circle_sizes": np.tile(10, number_of_columns),
        # Text for title and key items.
        "title_text": np.array(["Key"]),
        "text_1": np.array(["Horizon", "ZD=70 degrees", "Ecliptic", "Galactic plane"]),
        "text_2": np.array(["Moon position", "Sun position", "Survey field(s)", "Telescope pointing"]),
    }


def generate_key():
    """Populate a Bokeh plot with glyphs of key objects.

    Returns
    -------
    key : 'bokeh.models.Plot'
        A key for the dashboard map.
    """
    data_array = generate_array_for_key()

    # Assign data to relevant data source (to be used in glyph creation below).
    title_source = bokeh.models.ColumnDataSource(
        dict(
            x=data_array["x_title"],
            y=data_array["y_title"],
            text=data_array["title_text"],
        )
    )
    text1_source = bokeh.models.ColumnDataSource(
        dict(
            x=data_array["x_text_1"],
            y=data_array["y"],
            text=data_array["text_1"],
        )
    )
    text2_source = bokeh.models.ColumnDataSource(
        dict(
            x=data_array["x_text_2"],
            y=data_array["y"],
            text=data_array["text_2"],
        )
    )
    circle_source = bokeh.models.ColumnDataSource(
        dict(
            x=data_array["x_circles"],
            y=data_array["y"],
            sizes=data_array["circle_sizes"],
            colours=data_array["circle_colours"],
        )
    )
    line_source = bokeh.models.ColumnDataSource(
        dict(
            x0=data_array["x0_lines"],
            y0=data_array["y"],
            x1=data_array["x1_lines"],
            y1=data_array["y"],
            colours=data_array["line_colours"],
        )
    )

    # Create glyphs.
    border_glyph = bokeh.models.Rect(
        x=7,
        y=3.25,
        width=14,
        height=6.5,
        line_color="#048b8c",
        fill_color=None,
        line_width=3,
    )
    header_glyph = bokeh.models.Rect(
        x=7,
        y=5.75,
        width=14,
        height=1.5,
        line_color=None,
        fill_color="#048b8c",
    )
    title_glyph = bokeh.models.Text(
        x="x",
        y="y",
        text="text",
        text_font_size="15px",
        text_color="white",
        text_baseline="middle",
        text_font={"value": "verdana"},
        text_align="center",
    )
    text1_glyph = bokeh.models.Text(
        x="x",
        y="y",
        text="text",
        text_font_size="10px",
        text_color="black",
        text_baseline="middle",
        text_font={"value": "verdana"},
    )
    text2_glyph = bokeh.models.Text(
        x="x",
        y="y",
        text="text",
        text_font_size="10px",
        text_color="black",
        text_baseline="middle",
        text_font={"value": "verdana"},
    )
    circle_glyph = bokeh.models.Circle(
        x="x",
        y="y",
        size="sizes",
        line_color="colours",
        fill_color="colours",
    )
    line_glyph = bokeh.models.Segment(
        x0="x0",
        y0="y0",
        x1="x1",
        y1="y1",
        line_color="colours",
        line_width=2,
        line_cap="round",
    )

    key = bokeh.models.Plot(
        title=None,
        width=300,
        height=150,
        min_border=0,
        toolbar_location=None,
    )

    key.add_glyph(border_glyph)
    key.add_glyph(header_glyph)
    key.add_glyph(title_source, title_glyph)
    key.add_glyph(text1_source, text1_glyph)
    key.add_glyph(text2_source, text2_glyph)
    key.add_glyph(circle_source, circle_glyph)
    key.add_glyph(line_source, line_glyph)

    return key


# ----------------------------------------------------------- Create dashboard


# Initialize the dashboard layout.
sched_app = pn.GridSpec(
    sizing_mode="stretch_both",
    max_height=1000,
).servable()


def scheduler_app(date=None, scheduler_pickle=None):
    """Create a dashboard with grids of Param parameters, Tabulator widgets,
    and Bokeh plots.

    Parameters
    ----------
    date : 'datetime' or 'date', optional
        The date/datetime of interest. The default is None.
    scheduler_pickle : 'str', optional
        A filepath or URL for the scheduler pickle. The default is None.

    Returns
    -------
    sched_app : 'panel.layout.grid.GridSpec'
        The dashboard.
    """
    scheduler = Scheduler()

    if date is not None:
        scheduler.date = date

    if scheduler_pickle is not None:
        scheduler.scheduler_fname = scheduler_pickle

    # Dashboard title.
    sched_app[0:8, :] = pn.Row(
        pn.Column(
            pn.Spacer(height=4),
            pn.pane.Str(
                "Scheduler Dashboard",
                height=20,
                styles={"font-size": "16pt", "font-weight": "500", "color": "white"},
                stylesheets=[stylesheet],
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
    # Parameter inputs (pickle, date, tier).
    sched_app[8:33, 0:21] = pn.Param(
        scheduler,
        parameters=["scheduler_fname", "date", "USER_tier"],
        widgets={
            "scheduler_fname": {
                "widget_type": pn.widgets.TextInput,
                "placeholder": "filepath or URL of pickle",
            },
            "date": pn.widgets.DatetimePicker,
        },
        name="Select pickle file, date and tier.",
    )
    # Survey rewards table and header.
    sched_app[8:33, 21:67] = pn.Row(
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
        sizing_mode="stretch_height",
    )
    # Reward table and header.
    sched_app[33:87, 0:67] = pn.Row(
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
    sched_app[8:59, 67:100] = pn.Column(
        pn.Spacer(height=10),
        pn.Row(
            scheduler.map_title,
            styles={"background": "#048b8c"},
        ),
        pn.param.ParamMethod(scheduler.publish_sky_map, loading_indicator=True),
    )
    # Key.
    sched_app[66:87, 67:87] = pn.Column(
        pn.Spacer(height=32),
        pn.pane.Bokeh(generate_key()),
    )
    # Map display parameters (map, nside, color palette).
    sched_app[66:87, 87:100] = pn.Param(
        scheduler,
        parameters=["survey_map", "nside", "color_palette"],
        show_name=False,
    )
    # Debugging collapsable card.
    sched_app[87:100, :] = pn.Card(
        pn.Column(
            scheduler._debugging_messages,
            styles={"background": "#EDEDED"},
        ),
        title="Debugging",
        header_background="white",
        styles={"background": "#048b8c"},
        sizing_mode="stretch_width",
        collapsed=True,
    )

    return sched_app


def main():
    print("Starting scheduler dashboard.")

    if "SCHEDULER_PORT" in os.environ:
        scheduler_port = int(os.environ["SCHEDULER_PORT"])
    else:
        scheduler_port = 8080

    assets_dir = os.path.join(importlib.resources.files("schedview"), "app", "scheduler_dashboard", "assets")

    pn.serve(
        scheduler_app,
        port=scheduler_port,
        title="Scheduler Dashboard",
        show=True,
        start=True,
        autoreload=True,
        threaded=True,
        static_dirs={"assets": assets_dir},
    )


if __name__ == "__main__":
    main()
