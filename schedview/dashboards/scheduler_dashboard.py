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

import bokeh
import logging
import numpy as np
import os
import panel as pn
import param
import traceback

from astropy.time import Time
from bokeh.models.widgets.tables import HTMLTemplateFormatter, BooleanFormatter
from datetime import datetime
from pandas import Timestamp
from pytz import timezone
from zoneinfo import ZoneInfo

import schedview
import schedview.collect.scheduler_pickle
import schedview.compute.scheduler
import schedview.compute.survey
import schedview.plot.survey

# For the conditions.mjd bugfix
from rubin_sim.scheduler.model_observatory import ModelObservatory

"""

NEXT
----

    0. Check over old GridSpec file and make sure I haven't forgotten to copy anything over.
    1. Rename parameters (leading underscore; display_headings -> display_dashboard_data).
    2. Basis function table widths need updating when table is updated. [CASE: tier 1 > tier 3]
    3. Run early code and see if it was possible to open dashboard in another tab.
    4. pytests.
    5. Pop-out debugger.
    8. In dashboard title, replace self.survey with first character of survey name.
    9. Reorder functions.
   10. Finish docstrings
   11. Is there a neater way to apply URL formatting to the columns so that it doesn't show in titles?
   12. Move the dashboard to the app folder.


[Code ordering, from LSST DM guide]

    1. Shebang line, #! /usr/bin/env python (only for executable scripts)
    2. Module-level comments (such as the license statement)
    3. Module-level docstring
    4. __all__ = [...] statement, if present
    5. Imports
    6. Private module variables (names start with underscore)
    7. Private module functions and classes (names start with underscore)
    8. Public module variables
    9. Public functions and classes

/Users/me/Documents/2023/ADACS/Panel_scheduler/Rubin_scheduler_dashboard/example_pickle_scheduler.p.xz
"""

DEFAULT_CURRENT_TIME = Time.now()
DEFAULT_TIMEZONE = 'America/Santiago'
COLOR_PALETTES = [color for color in bokeh.palettes.__palettes__ if '256' in color]
LOGO = '/assets/lsst_white_logo.png'

pn.extension(
    'tabulator',
    sizing_mode='stretch_width',
    notifications=True,
    )

logging.basicConfig(
    format='%(asctime)s %(message)s',
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
    if dataframe_row[url_column] == '':
        return dataframe_row[name_column]
    else:
        return f'<a href="{dataframe_row[url_column]}" target="_blank"> {dataframe_row[name_column]}</a>'


class Scheduler(param.Parameterized):
    """A Parametrized container for parameters, data, and panel objects for the
    scheduler dashboard.
    """

    # TODO: Clean up parameters.

    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
    Such a pickle file can either be of an instance of a subclass of
    rubin_sim.scheduler.schedulers.CoreScheduler, or a tuple of the form
    (scheduler, conditions), where scheduler is an instance of a subclass of
    rubin_sim.scheduler.schedulers.CoreScheduler, and conditions is an
    instance of rubin_sim.scheduler.conditions.Conditions.
    """
    scheduler_fname = param.String(
        default='',
        label='Scheduler pickle file',
        doc=scheduler_fname_doc,
        )
    # scheduler_fname = param.Path(default='scheduler.p', search_paths=['/'])
    date = param.Date(
        default=DEFAULT_CURRENT_TIME.datetime.date(),
        doc='')
    USER_tier = param.ObjectSelector(
        default='',
        objects=[''],
        label='Tier',
        doc='The label for the first index into the CoreScheduler.survey_lists.',
        )
    survey_map = param.ObjectSelector(
        default='reward',
        objects=['reward'],
        doc='Survey sky brightness maps, basis functions with non-scalar values and reward map.',
        )
    nside = param.ObjectSelector(
        default=16,
        objects=[2**n for n in np.arange(1, 6)],
        label='Map resolution (nside)',
        doc='',
        )
    color_palette = param.ObjectSelector(
        default='Viridis256',
        objects=COLOR_PALETTES,
        doc=''
        )

    _survey_df_widget = param.Parameter(None)
    _basis_function_df_widget = param.Parameter(None)

    publish_survey_widget = param.Parameter(None)
    publish_bf_widget = param.Parameter(None)
    publish_map = param.Parameter(None)

    update_titles = param.Parameter(None)
    show_loading_indicator = False

    _debugging_message = param.Parameter(None)

    tier = None
    survey = 0
    basis_function = -1
    _debug_string = ''

    _scheduler = None
    _conditions = None
    _date_time = None
    _rewards = None
    _survey_rewards = None
    _survey_maps = None
    _basis_functions = None

    sky_map_base = None

    display_basis_function = False
    _display_headings = False
    do_not_trigger_update = True

    # model_observatory = ModelObservatory()

    # -------------------------------------------------------------------------------------- Dashboard titles

    # TODO: replace self.survey with first character of survey name (surveys aren't in order in big pickle)
    # TODO: check if being out of order has consequences anywhere else
    # TODO: Re-order functions.

    def generate_dashboard_title(self):
        """

        Returns
        -------
        str
            DESCRIPTION.
        """
        if not self._display_headings:
            return ''
        if not self.display_basis_function:
            return f'\nTier {self.tier[-1]} - Survey {self.survey} - Map {self.survey_map}'
        elif self.display_basis_function and self.basis_function >= 0:
            return f'\nTier {self.tier[-1]} - Survey {self.survey} - Basis function {self.basis_function}'
        else:
            return f'\nTier {self.tier[-1]} - Survey {self.survey}'

    def generate_survey_rewards_title(self):
        """

        Returns
        -------
        str
            DESCRIPTION.
        """
        if not self._display_headings or self._scheduler is None or self.tier == '':
            return 'Surveys and rewards'
        else:
            return f'Surveys and rewards for tier {self.tier[-1]}'

    def generate_basis_function_table_title(self):
        """

        Returns
        -------
        str
            DESCRIPTION.
        """
        if not self._display_headings or self._scheduler is None:
            return 'Basis functions'
        else:
            survey_name = self._survey_rewards[self._survey_rewards['tier'] ==
                                               self.tier].reset_index()['survey'][self.survey]
            return f'Basis functions for survey {survey_name}'

    def generate_map_title(self):
        """

        Returns
        -------
        str
            DESCRIPTION.
        """
        if not self._display_headings or self._scheduler is None:
            return 'Map'
        survey_name = self._survey_rewards[self._survey_rewards['tier'] ==
                                           self.tier].reset_index()['survey'][self.survey]
        if not self.display_basis_function:
            return f'Survey {survey_name}\nMap: {self.survey_map}'
        elif self.display_basis_function and self.basis_function >= 0:
            bf_name = self._basis_functions['basis_func'][self.basis_function]
            return f'Survey {survey_name}\nBasis function {self.basis_function}: {bf_name}'
        else:
            return f'Survey {survey_name}\n'

    @param.depends('update_titles')
    def dashboard_title(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        title_string = self.generate_dashboard_title()
        return pn.pane.Str(
            title_string,
            height=20,
            styles={'font-size': '14pt',
                    'font-weight': '300',
                    'color': 'white'},
            stylesheets=[stylesheet],
            )

    @param.depends('update_titles')
    def survey_rewards_title(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        title_string = self.generate_survey_rewards_title()
        return pn.pane.Str(
            title_string,
            styles={'font-size': '13pt',
                    'font-weight': '300',
                    'color': 'white'},
            stylesheets=[stylesheet]
            )

    @param.depends('update_titles')
    def basis_function_table_title(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        title_string = self.generate_basis_function_table_title()
        return pn.pane.Str(
            title_string,
            styles={'font-size': '13pt',
                    'font-weight': '300',
                    'color': 'white'},
            stylesheets=[stylesheet],
            css_classes=['title']
            )

    @param.depends('update_titles')
    def map_title(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        title_string = self.generate_map_title()
        return pn.pane.Str(
            title_string,
            styles={'font-size': '13pt',
                    'font-weight': '300',
                    'color': 'white'},
            stylesheets=[stylesheet]
            )

    # ------------------------------------------------------------------------------------------ User actions

    @param.depends('scheduler_fname', watch=True)
    def _update_scheduler_fname(self):
        """Update the dashboard when a user enters a new filepath/URL."""
        self.show_loading_indicator = True
        self.clear_dashboard()

        if not self.read_scheduler():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if not self.make_summary_df():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        self.create_survey_tabulator_widget()
        self.param.trigger('publish_survey_widget')

        self.compute_survey_maps()
        self.survey_map = self.param['survey_map'].objects[-1]

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

        self.make_survey_reward_dataframe()
        self.create_basis_function_tabulator_widget()
        self.param.trigger('publish_bf_widget')

        self._display_headings = True
        self.display_basis_function = False
        self.param.trigger('update_titles')

        self.show_loading_indicator = False

    @param.depends('date', watch=True)
    def _update_date(self):
        """Update the dashboard when a user chooses a new date/time."""
        self.show_loading_indicator = True
        self.clear_dashboard()

        self._date_time = Time(Timestamp(
            self.date,
            tzinfo=ZoneInfo(DEFAULT_TIMEZONE),
            )).mjd

        if not self.make_summary_df():
            self.clear_dashboard()
            self.show_loading_indicator = False
            return

        if self._survey_df_widget is None:
            self.create_survey_tabulator_widget()
        else:
            self.update_survey_tabulator_widget()
        self.param.trigger('publish_survey_widget')

        self.compute_survey_maps()
        self.survey_map = self.param['survey_map'].objects[-1]

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

        self.make_survey_reward_dataframe()
        self.create_basis_function_tabulator_widget()
        self.param.trigger('publish_bf_widget')

        self._display_headings = True
        self.display_basis_function = False
        self.param.trigger('update_titles')

        self.show_loading_indicator = False

    @param.depends('USER_tier', watch=True)
    def _update_tier(self):
        """Update the dashboard when a user chooses a new tier."""
        if not self._display_headings:
            return

        self.tier = self.USER_tier
        self.survey = 0

        if self._survey_df_widget is None:
            self.create_survey_tabulator_widget()
        else:
            self.update_survey_tabulator_widget()
        self.param.trigger('publish_survey_widget')

        self.compute_survey_maps()
        self.do_not_trigger_update = True
        self.survey_map = self.param['survey_map'].objects[-1]
        self.do_not_trigger_update = False

        self.make_survey_reward_dataframe()
        if self._basis_function_df_widget is None:
            self.create_basis_function_tabulator_widget()
        else:
            self.update_basis_function_tabulator_widget()
        self.param.trigger('publish_bf_widget')

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

        self.display_basis_function = False
        self.param.trigger('update_titles')

    @param.depends('_survey_df_widget.selection', watch=True)
    def _update_survey(self):
        """Update the dashboard when a user selects a survey."""
        if self._survey_df_widget.selection == []:
            return

        self.survey = self._survey_df_widget.selection[0]

        self.compute_survey_maps()
        self.do_not_trigger_update = True
        self.survey_map = self.param['survey_map'].objects[-1]
        self.do_not_trigger_update = False

        self.make_survey_reward_dataframe()
        if self._basis_function_df_widget is None:
            self.create_basis_function_tabulator_widget()
        else:
            self.update_basis_function_tabulator_widget()
        self.param.trigger('publish_bf_widget')

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

        self.display_basis_function = False
        self.param.trigger('update_titles')

    @param.depends('_basis_function_df_widget.selection', watch=True)
    def _update_basis_function(self):
        """Update the dashboard when a user selects a basis function."""
        if self._basis_function_df_widget.selection == []:
            return

        self.basis_function = self._basis_function_df_widget.selection[0]

        self.update_sky_map_with_basis_function()
        self.param.trigger('publish_map')

        self.display_basis_function = True
        self.param.trigger('update_titles')

    @param.depends('survey_map', watch=True)
    def _update_survey_map(self):
        """Update the dashboard when a user chooses a new survey map."""
        # Don't run code during initial load or when updating tier or survey.
        if not self._display_headings or self.do_not_trigger_update:
            return

        if self._basis_function_df_widget is not None:
            self._basis_function_df_widget.selection = []

        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

        self.display_basis_function = False
        self.param.trigger('update_titles')

    @param.depends('nside', watch=True)
    def _update_nside(self):
        """Update the dashboard when a user chooses a new nside."""
        # Don't run code during initial load.
        if not self._display_headings:
            return

        self.compute_survey_maps()

        self.create_sky_map_base()
        self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

    @param.depends('color_palette', watch=True)
    def _update_color_palette(self):
        """Update the dashboard when a user chooses a new color palette."""
        if self.display_basis_function:
            self.update_sky_map_with_basis_function()
        else:
            self.update_sky_map_with_survey_map()
        self.param.trigger('publish_map')

    # ------------------------------------------------------------------------------------- Internal workings

    def clear_dashboard(self):
        """Clear the dashboard for a new pickle or a new date."""
        self._survey_df_widget = None
        self._basis_functions = None
        self.sky_map_base = None
        self._display_headings = False

        self.param.trigger('publish_survey_widget')
        self.param.trigger('publish_bf_widget')
        self.param.trigger('publish_map')
        self.param.trigger('update_titles')

        self.param['USER_tier'].objects = ['']
        self.param['survey_map'].objects = ['']

        self.USER_tier = ''
        self.tier = ''
        self.survey_map = ''

        self.survey = 0
        self.basis_function = -1

    def read_scheduler(self):
        """Loads the scheduler and conditions objects from scheduler_fname.

        Returns
        -------
        bool
            Record of success or failure of read_scheduler().
        """
        try:
            pn.state.notifications.info('Scheduler loading...', duration=0)
            logging.info('Reading scheduler and conditions.')

            (scheduler, conditions) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)
            self._scheduler = scheduler
            self._conditions = conditions

            pn.state.notifications.clear()
            pn.state.notifications.success('Scheduler pickle loaded successfully!')

            return True

        except Exception:
            tb = traceback.format_exc(limit=-1)
            logging.error(f'Could not load scheduler from {self.scheduler_fname} \n{tb}')
            pn.state.notifications.clear()
            pn.state.notifications.error(f'Could not load scheduler from {self.scheduler_fname}', duration=0)

            self._scheduler = None
            self._conditions = None

            return False

    def make_summary_df(self):
        """Update conditions, and make reward and scheduler summary dataframes.

        Returns
        -------
        bool
            Record of success of conditions update and dataframe construction.
        """
        if self._scheduler is None:
            logging.info('Cannot update survey reward table as no pickle is loaded.')

            return False

        try:
            pn.state.notifications.info('Making scheduler summary dataframe...', duration=0)
            logging.info('Making scheduler summary dataframe.')

            # TODO: Conditions setter bug-fix.
            self._conditions.mjd = self._date_time
            # self._conditions.__dict__.clear()
            # self._conditions.__dict__.update(model_observatory.return_conditions().__dict__)

            # if self.model_observatory.nside != self._scheduler.nside:
            #     logging.info(f'Creating new ModelObservatory() with nside={self._scheduler.nside}.')
            #     self.model_observatory = ModelObservatory(nside=self._scheduler.nside)
            # self.model_observatory.mjd = self._date_time
            # self._conditions = self.model_observatory.return_conditions()

            self._scheduler.update_conditions(self._conditions)
            self._rewards = self._scheduler.make_reward_df(self._conditions)
            survey_rewards = schedview.compute.scheduler.make_scheduler_summary_df(
                self._scheduler,
                self._conditions,
                self._rewards,
                )

            # TODO: Is there a neater way to apply URL formatting to columns (rather than duplicating?).

            # Duplicate column and apply URL formatting to one of the columns.
            survey_rewards['survey'] = survey_rewards.loc[:, 'survey_name']
            survey_rewards['survey_name'] = survey_rewards.apply(
                url_formatter,
                axis=1,
                args=('survey_name', 'survey_url'),
                )
            self._survey_rewards = survey_rewards

            tiers = self._survey_rewards.tier.unique().tolist()
            self.param['USER_tier'].objects = tiers
            self.USER_tier = tiers[0]
            self.tier = tiers[0]
            self.survey = 0

            pn.state.notifications.clear()
            pn.state.notifications.success('Scheduler summary dataframe updated successfully')

            return True

        except Exception:
            tb = traceback.format_exc(limit=-1)
            logging.info(f'Scheduler summary dataframe unable to be updated: \n{tb}')
            pn.state.notifications.clear()
            pn.state.notifications.error('Scheduler summary dataframe unable to be updated!', duration=0)
            self._survey_rewards = None

            return False

    def create_survey_tabulator_widget(self):
        """Create Tabulator widget with scheduler summary dataframe."""
        if self._survey_rewards is None:
            return

        logging.info('Creating survey widget.')

        tabulator_formatter = {'survey_name': HTMLTemplateFormatter(template='<%= value %>')}
        columns = [
            'tier',
            'survey_name',
            'reward',
            'survey',
            'survey_url',
            ]
        titles = {
            'survey_name': 'Survey Name',
            'reward': 'Reward',
            }
        survey_rewards_table = pn.widgets.Tabulator(
            self._survey_rewards[self._survey_rewards['tier'] == self.tier][columns],
            widths={'survey_name': '60%',
                    'reward': '40%'},
            show_index=False,
            formatters=tabulator_formatter,
            titles=titles,
            disabled=True,
            selectable=1,
            hidden_columns=['tier', 'survey', 'survey_url'],
            pagination='remote',
            page_size=4,
            sizing_mode='stretch_width',
            )
        self._survey_df_widget = survey_rewards_table

    def update_survey_tabulator_widget(self):
        """Updates data for survey Tabulator widget."""
        logging.info('Updating survey widget.')

        columns = [
            'tier',
            'survey_name',
            'reward',
            'survey',
            'survey_url',
            ]
        self._survey_df_widget._update_data(
            self._survey_rewards[self._survey_rewards['tier'] == self.tier][columns])

    @param.depends('publish_survey_widget')
    def publish_survey_tabulator_widget(self):
        """Publishes the survey Tabulator widget to be displayed on dashboard.

        Returns
        -------
        panel.widgets.Tabulator
            Table of survey data from scheduler summary dataframe.

        """
        if self._survey_df_widget is None:
            return 'No surveys available.'
        else:
            return self._survey_df_widget

    def compute_survey_maps(self):
        """Compute survey maps and update drop-down selection."""
        if self._scheduler is None:
            logging.info('Cannot compute survey maps as no scheduler loaded.')
            return
        if self._survey_rewards is None:
            logging.info('Cannot compute survey maps as no scheduler summary made.')
            return
        try:
            logging.info('Computing survey maps.')

            self._survey_maps = schedview.compute.survey.compute_maps(
                self._scheduler.survey_lists[int(self.tier[-1])][self.survey],
                self._conditions,
                self.nside,
                )
            self.param['survey_map'].objects = list(self._survey_maps.keys())

        except Exception:
            logging.info(f'Cannot compute survey maps: \n{traceback.format_exc(limit=-1)}')

    def make_survey_reward_dataframe(self):
        """Make the survey reward dataframe."""
        if self._scheduler is None:
            logging.info('Cannot make survey reward dataframe as no scheduler loaded.')
            return
        if self._survey_rewards is None:
            logging.info('Cannot make survey reward dataframe as no scheduler summary made.')
            return
        try:
            logging.info('Making survey reward dataframe.')

            # Survey has basis functions.
            if self._rewards.index.isin([(int(self.tier[-1]), self.survey)]).any():

                basis_function_df = schedview.compute.survey.make_survey_reward_df(
                    self._scheduler.survey_lists[int(self.tier[-1])][self.survey],
                    self._conditions,
                    self._rewards.loc[[(int(self.tier[-1]), self.survey)], :]
                    )
                # Duplicate column and apply URL formatting to one of the columns.
                basis_function_df['basis_func'] = basis_function_df.loc[:, 'basis_function']
                basis_function_df['basis_function'] = basis_function_df.apply(
                    url_formatter,
                    axis=1,
                    args=('basis_function', 'doc_url'),
                    )
                self._basis_functions = basis_function_df
            else:
                self._basis_functions = None

        except Exception:
            logging.info(f'Cannot make survey reward dataframe: \n{traceback.format_exc(limit=-1)}')

    def create_basis_function_tabulator_widget(self):
        """Create Tabulator widget with survey reward dataframe."""
        if self._basis_functions is None:
            return

        logging.info('Creating basis function widget.')

        tabulator_formatter = {
            'basis_function': HTMLTemplateFormatter(template='<%= value %>'),
            'feasible': BooleanFormatter(),
            }
        columns = [
            'basis_function',
            'basis_function_class',
            'feasible',
            'max_basis_reward',
            'basis_area',
            'basis_weight',
            'max_accum_reward',
            'accum_area',
            'doc_url',
            'basis_func',
            ]
        titles = {
            'basis_function': 'Basis Function',
            'basis_function_class': 'Class',
            'feasible': 'Feasible',
            'max_basis_reward': 'Max Reward',
            'basis_area': 'Area',
            'basis_weight': 'Weight',
            'max_accum_reward': 'Max Accumulated Reward',
            'accum_area': 'Accumulated Area',
            }
        basis_function_table = pn.widgets.Tabulator(
            self._basis_functions[columns],
            titles=titles,
            layout='fit_data',
            show_index=False,
            formatters=tabulator_formatter,
            disabled=True,
            frozen_columns=['basis_function'],
            hidden_columns=['basis_func', 'doc_url'],
            selectable=1,
            pagination='remote',
            page_size=13,
            )
        self._basis_function_df_widget = basis_function_table

    # ------------------------------------------------------------------------- <- docstring length limit
    def update_basis_function_tabulator_widget(self):
        """."""
        if self._basis_functions is None:
            return

        logging.info('Updating basis function widget.')

        self._basis_function_df_widget.selection = []
        columns = [
            'basis_function',
            'basis_function_class',
            'feasible',
            'max_basis_reward',
            'basis_area',
            'basis_weight',
            'max_accum_reward',
            'accum_area',
            'doc_url',
            'basis_func',
            ]
        self._basis_function_df_widget._update_data(self._basis_functions[columns])
        # TODO: reset column widths

    # ------------------------------------------------------------------------- <- docstring length limit
    @param.depends('publish_bf_widget')
    def publish_basis_function_widget(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        if self._basis_functions is None:
            return 'No basis functions available.'
        else:
            return self._basis_function_df_widget

    # ------------------------------------------------------------------------- <- docstring length limit
    def create_sky_map_base(self):
        """."""
        if self._survey_maps is None:
            logging.info('Cannot create sky map as no survey maps made.')
            return

        try:
            logging.info('Creating sky map.')

            # Make a dummy map that is 1.0 for all healpixels that might have data.
            self._survey_maps['above_horizon'] = np.where(self._conditions.alt > 0, 1.0, np.nan)
            self.sky_map_base = schedview.plot.survey.map_survey_healpix(
                self._conditions.mjd,
                self._survey_maps,
                'above_horizon',
                self.nside,
                )
            self.sky_map_base.plot.toolbar.tools[-1].tooltips.remove(('above_horizon', '@above_horizon'))

        except Exception:
            logging.info(f'Cannot create sky map: \n{traceback.format_exc(limit=-1)}')

    # ------------------------------------------------------------------------- <- docstring length limit
    def update_sky_map_with_survey_map(self):
        """.

        Notes
        -----
        There are three possible update cases:
         - Case 1: Selection is a basis function.
         - Case 2: Selection is a survey map and is all NaNs.
         - Case 3: Selection is a survey map and is not all NaNs.
        """
        if self.sky_map_base is None:
            'Cannot update sky map with survey map as no base map loaded.'
            return

        logging.info('Updating sky map with survey map.')

        # Update figure to show a different map by modifying the existing bokeh objects and pushing update.
        hpix_renderer = self.sky_map_base.plot.select(name='hpix_renderer')[0]
        hpix_data_source = self.sky_map_base.plot.select(name='hpix_ds')[0]

        # Selection is a basis function.
        if self.survey_map not in ['u_sky', 'g_sky', 'r_sky', 'i_sky', 'z_sky', 'y_sky', 'reward']:

            logging.info('CASE 1')

            basis_function_name = self.survey_map.split('@')[0].strip()
            bf_underscored = basis_function_name.replace(' ', '_')
            bf_survey_key = list(key for key in self._survey_maps if basis_function_name in key)[0]
            bf_bokeh_key = list(key for key in hpix_data_source.data if bf_underscored in key)[0]

            min_good_value = np.nanmin(self._survey_maps[bf_survey_key])
            max_good_value = np.nanmax(self._survey_maps[bf_survey_key])

            if min_good_value == max_good_value:
                min_good_value -= 1
                max_good_value += 1

            hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                field_name=bf_bokeh_key,
                palette=self.color_palette,
                low=min_good_value,
                high=max_good_value,
                nan_color='white',
                )
        # Selection is a survey map and is all NaNs.
        elif np.isnan(self._survey_maps[self.survey_map]).all():

            logging.info('CASE 2')

            hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                field_name=self.survey_map,
                palette=self.color_palette,
                low=-1,
                high=1,
                nan_color='white',
                )
        # Selection is a survey map and is not all NaNs.
        else:
            logging.info('CASE 3')

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
                nan_color='white',
                )
        hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
        self.sky_map_base.update()

    # ------------------------------------------------------------------------- <- docstring length limit
    def update_sky_map_with_basis_function(self):
        """."""
        if self.sky_map_base is None:
            'Cannot update sky map with basis function as no base map loaded.'
            return

        try:
            logging.info('Updating sky map with basis function.')

            hpix_renderer = self.sky_map_base.plot.select(name='hpix_renderer')[0]
            hpix_data_source = self.sky_map_base.plot.select(name='hpix_ds')[0]

            basis_function_name = self._basis_functions['basis_func'][self.basis_function]
            bf_underscored = basis_function_name.replace(' ', '_')

            # Basis function is not scalar.
            if any(basis_function_name in key for key in self._survey_maps):

                logging.info('CASE 4')

                bf_survey_key = list(key for key in self._survey_maps if basis_function_name in key)[0]
                bf_bokeh_key = list(key for key in hpix_data_source.data if bf_underscored in key)[0]

                min_good_value = np.nanmin(self._survey_maps[bf_survey_key])
                max_good_value = np.nanmax(self._survey_maps[bf_survey_key])

                if min_good_value == max_good_value:
                    min_good_value -= 1
                    max_good_value += 1

                # Modify existing bokeh object.
                hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                    field_name=bf_bokeh_key,
                    palette=self.color_palette,
                    low=min_good_value,
                    high=max_good_value,
                    nan_color='white',
                    )
            else:
                max_basis_reward = self._basis_functions.loc[self.basis_function, :]['max_basis_reward']

                # Basis function is scalar and finite.
                if max_basis_reward != -np.inf:

                    logging.info('CASE 5')

                    # Create array populated with scalar values where sky brightness map is not NaN.
                    scalar_array = hpix_data_source.data['u_sky'].copy()
                    scalar_array[~np.isnan(hpix_data_source.data['u_sky'])] = max_basis_reward
                    hpix_data_source.data[bf_underscored] = scalar_array

                    hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                        field_name=bf_underscored,
                        palette=self.color_palette,
                        low=max_basis_reward-1,
                        high=max_basis_reward+1,
                        nan_color='white',
                        )
                # Basis function is scalar and -inf.
                else:
                    logging.info('CASE 6')

                    hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                        field_name=self._basis_functions['basis_func'][self.basis_function],
                        palette='Greys256',
                        low=-1,
                        high=1,
                        nan_color='white',
                        )
            hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
            self.sky_map_base.update()

        except Exception:
            logging.info(f'Could not load map: \n{traceback.format_exc(limit=-1)}')

    # ------------------------------------------------------------------------- <- docstring length limit
    @param.depends('publish_map')
    def publish_sky_map(self):
        """

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        if self._conditions is None:
            return 'No scheduler loaded.'

        elif self._survey_maps is None:
            return 'No surveys are loaded.'

        elif self.sky_map_base is None:
            return 'No map loaded.'

        else:
            logging.info('Publishing sky map.')
            return self.sky_map_base.figure

    @param.depends('_debugging_message')
    def debugging_messages(self):
        """

        Returns
        -------
        debugging_messages : TYPE
            DESCRIPTION.
        """
        if self._debugging_message is None:
            return None
        timestamp = datetime.now(timezone('America/Santiago')).strftime('%Y-%m-%d %H:%M:%S')
        self._debug_string = f'\n {timestamp} - {self._debugging_message}' + self._debug_string
        debugging_messages = pn.pane.Str(
            self._debug_string,
            height=70,
            styles={'font-size': '9pt',
                    'color': 'black',
                    'overflow': 'scroll'},
            )
        return debugging_messages

    # TODO: Update update_loading() name to something related to the loading indicator.

    @param.depends('show_loading_indicator', watch=True)
    def update_loading(self):
        """."""
        sched_app.loading = self.show_loading_indicator


# TODO: Should the key functions go before the Scheduler class?

def generate_array_for_key(number_of_columns=4):
    """

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
        'x_title': np.array([7]),    # Title x coord
        'y_title': np.array([5.75]),  # Title y coord
        'x_circles': np.tile(8, number_of_columns),     # Circle centre coords
        'x_text_1': np.tile(2.5, number_of_columns),   # Text in colunn 1
        'x_text_2': np.tile(8.75, number_of_columns),  # Text in column 2
        'x0_lines': np.tile(0.75, number_of_columns),  # Start lines
        'x1_lines': np.tile(2, number_of_columns),     # End lines
        'y': np.arange(number_of_columns, 0, -1),        # y coords for all items except title

        # Colours and sizes of images.
        'line_colours': np.array(['black', 'red', '#1f8f20', '#110cff']),
        'circle_colours': np.array(['#ffa500', 'grey', 'red', '#1f8f20']),
        'circle_sizes': np.tile(10, number_of_columns),

        # Text for title and key items.
        'title_text': np.array(['Key']),
        'text_1': np.array(['Horizon', 'ZD=70 degrees', 'Ecliptic', 'Galactic plane']),
        'text_2': np.array(['Moon position', 'Sun position', 'Survey field(s)', 'Telescope pointing']),
        }


# Generates the key as a Bokeh plot.
def generate_key():
    """

    Returns
    -------
    key : 'bokeh.models.Plot'
        DESCRIPTION.
    """
    data_array = generate_array_for_key()

    # Assign data to relevant data source (to be used in glyph creation below).
    title_source = bokeh.models.ColumnDataSource(dict(
        x=data_array['x_title'],
        y=data_array['y_title'],
        text=data_array['title_text'],
        ))
    text1_source = bokeh.models.ColumnDataSource(dict(
        x=data_array['x_text_1'],
        y=data_array['y'],
        text=data_array['text_1'],
        ))
    text2_source = bokeh.models.ColumnDataSource(dict(
        x=data_array['x_text_2'],
        y=data_array['y'],
        text=data_array['text_2'],
        ))
    circle_source = bokeh.models.ColumnDataSource(dict(
        x=data_array['x_circles'],
        y=data_array['y'],
        sizes=data_array['circle_sizes'],
        colours=data_array['circle_colours'],
        ))
    line_source = bokeh.models.ColumnDataSource(dict(
        x0=data_array['x0_lines'],
        y0=data_array['y'],
        x1=data_array['x1_lines'],
        y1=data_array['y'],
        colours=data_array['line_colours'],
        ))

    # Create glyphs.
    border_glyph = bokeh.models.Rect(
        x=7,
        y=3.25,
        width=14,
        height=6.5,
        line_color='#048b8c',
        fill_color=None,
        line_width=3,
        )
    header_glyph = bokeh.models.Rect(
        x=7,
        y=5.75,
        width=14,
        height=1.5,
        line_color=None,
        fill_color='#048b8c',
        )
    title_glyph = bokeh.models.Text(
        x='x',
        y='y',
        text='text',
        text_font_size='15px',
        text_color='white',
        text_baseline='middle',
        text_font={'value': 'verdana'},
        text_align='center',
        )
    text1_glyph = bokeh.models.Text(
        x='x',
        y='y',
        text='text',
        text_font_size='10px',
        text_color='black',
        text_baseline='middle',
        text_font={'value': 'verdana'},
        )
    text2_glyph = bokeh.models.Text(
        x='x',
        y='y',
        text='text',
        text_font_size='10px',
        text_color='black',
        text_baseline='middle',
        text_font={'value': 'verdana'},
        )
    circle_glyph = bokeh.models.Circle(
        x='x',
        y='y',
        size='sizes',
        line_color='colours',
        fill_color='colours',
        )
    line_glyph = bokeh.models.Segment(
        x0='x0',
        y0='y0',
        x1='x1',
        y1='y1',
        line_color='colours',
        line_width=2,
        line_cap='round',
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

# ----------------------------------------------------------------------------- <- docstring length limit


# Initialize the dashboard layout.
sched_app = pn.GridSpec(sizing_mode='stretch_both', max_height=1000).servable()


def scheduler_app(date=None, scheduler_pickle=None):
    """

    Parameters
    ----------
    date : TYPE, optional
        DESCRIPTION. The default is None.
    scheduler_pickle : TYPE, optional
        DESCRIPTION. The default is None.

    Returns
    -------
    sched_app : TYPE
        DESCRIPTION.
    """
    scheduler = Scheduler()

    if date is not None:
        scheduler.date = date

    if scheduler_pickle is not None:
        scheduler.scheduler_fname = scheduler_pickle

    # Dashboard title.
    sched_app[0:8, :] = pn.Row(
        pn.Column(pn.Spacer(height=4),
                  pn.pane.Str('Scheduler Dashboard',
                              height=20,
                              styles={'font-size': '16pt',
                                      'font-weight': '500',
                                      'color': 'white'},
                              stylesheets=[stylesheet],
                              ),
                  scheduler.dashboard_title,
                  ),
        pn.layout.HSpacer(),
        pn.pane.PNG(LOGO,
                    sizing_mode='scale_height',
                    align='center', margin=(5, 5, 5, 5),
                    ),
        sizing_mode='stretch_width',
        styles={'background': '#048b8c'},
        )
    # Parameter inputs (pickle, date, tier).
    sched_app[8:33, 0:21] = pn.Param(
        scheduler,
        parameters=['scheduler_fname', 'date', 'USER_tier'],
        widgets={'scheduler_fname': {'widget_type': pn.widgets.TextInput,
                                     'placeholder': 'filepath or URL of pickle'},
                 'date': pn.widgets.DatetimePicker},
        name='Select pickle file, date and tier.',
        )
    # Survey rewards table and header.
    sched_app[8:33, 21:67] = pn.Row(
        pn.Spacer(width=10),
        pn.Column(pn.Spacer(height=10),
                  pn.Row(scheduler.survey_rewards_title,
                         styles={'background': '#048b8c'},
                         ),
                  pn.param.ParamMethod(scheduler.publish_survey_tabulator_widget, loading_indicator=True),
                  ),
        pn.Spacer(width=10),
        sizing_mode='stretch_height',
        )
    # Basis function table and header.
    sched_app[33:87, 0:67] = pn.Row(
        pn.Spacer(width=10),
        pn.Column(pn.Spacer(height=10),
                  pn.Row(scheduler.basis_function_table_title,
                         styles={'background': '#048b8c'},
                         ),
                  pn.param.ParamMethod(scheduler.publish_basis_function_widget, loading_indicator=True)),
        pn.Spacer(width=10),
        )
    # Map display and header.
    sched_app[8:59, 67:100] = pn.Column(
        pn.Spacer(height=10),
        pn.Row(scheduler.map_title,
               styles={'background': '#048b8c'},
               ),
        pn.param.ParamMethod(scheduler.publish_sky_map, loading_indicator=True)
        )
    # Key.
    sched_app[66:87, 67:87] = pn.Column(
        pn.Spacer(height=32),
        pn.pane.Bokeh(generate_key()),
        )
    # Map display parameters (map, nside, color palette).
    sched_app[66:87, 87:100] = pn.Param(
        scheduler,
        parameters=['survey_map', 'nside', 'color_palette'],
        show_name=False,
        )
    # Debugging collapsable card.
    sched_app[87:100, :] = pn.Card(
        pn.Column(scheduler.debugging_messages,
                  styles={'background': '#EDEDED'},
                  ),
        title='Debugging',
        header_background='white',
        styles={'background': '#048b8c'},
        sizing_mode='stretch_width',
        collapsed=True,
        )

    return sched_app


if __name__ == '__main__':
    print('Starting scheduler dashboard.')

    if 'SCHEDULER_PORT' in os.environ:
        scheduler_port = int(os.environ['SCHEDULER_PORT'])
    else:
        scheduler_port = 8080

    pn.serve(
        scheduler_app,
        port=scheduler_port,
        title='Scheduler Dashboard',
        show=True,
        start=True,
        autoreload=True,
        threaded=True,
        static_dirs={'assets': './assets'}
    )
