import param
import pandas as pd
import panel as pn
import numpy as np   # used once; not really neccessary
import bokeh
import logging
import os
import traceback

from astropy.time import Time
from zoneinfo import ZoneInfo
from bokeh.models.widgets.tables import HTMLTemplateFormatter, BooleanFormatter

# Packages required for debugging timestamp option 2
from datetime import datetime
from pytz import timezone

import schedview
import schedview.compute.scheduler
import schedview.compute.survey
import schedview.collect.scheduler_pickle
import schedview.plot.survey

# For the conditions.mjd bugfix. (TEMPORARY)
from rubin_sim.scheduler.model_observatory import ModelObservatory


"""

NOTES
-----

I have created watcher functions separated into user actions.
I have grouped internal code based on how it is required across the possible actions.

I have NOT YET added in ALL try/except blocks, error notifications and debugging messages.

I have started writing pytests.
    
nside and color palette are not reset when a new pickle is loaded. I think this is okay.

CURRENT: refactoring
-------

    1. sky_map()
    2. Rewrite map title to remove nested if statement.
    3. Rewrite 3x titles like dashboard title (split in two).
    4. Rename display_headings to display_dashboard_data.
    5. Basis function table widths need updating when table is updated. [CASE: tier 1 > tier 3]
    

NEXT
----
    
    1. Run early code and see if it was possible to open dashboard in another tab.
    2. pytests.
    3. Since survey_map is modifiable by the user, _update_survey_map() is being
       triggered when new file, new date, new tier, new survey chosen. Also, same
       problem with tier when a new pickle is loaded straight after another pickle. 
       ** Wasn't there a way to set a parameter quietly?
    4. Pop-out debugger.
  

/Users/me/Documents/2023/ADACS/Panel_scheduler/Rubin_scheduler_dashboard/example_pickle_scheduler.p.xz


"""


COLOR_PALETTES = [s for s in bokeh.palettes.__palettes__ if "256" in s]
LOGO = "/assets/lsst_white_logo.png"


pn.extension(
    "tabulator",
    sizing_mode = "stretch_width",
    notifications=True
    )

logging.basicConfig(
    format = "%(asctime)s %(message)s",
    level  = logging.INFO
    )


def survey_url_formatter(row):
    """
    format survey name as a HTML href to survey url (if url exists)
    otherwise return survey name as a string
    row: a dataframe row
    """
    name = row['survey_name']
    url = row['survey_url']
    html = name if url == "" else f'<a href="{url}" target="_blank"> {name}</a>'
    return html

def basis_function_url_formatter(row):
    """
    format survey name as a HTML href to survey url (if url exists)
    otherwise return survey name as a string
    row: a dataframe row
    """
    name = row['basis_function']
    url = row['doc_url']
    html = name if url == "" else f'<a href="{url}" target="_blank"> {name}</a>'
    return html


# Change styles using CSS variables.
title_stylesheet = """
    :host {
        --mono-font: Helvetica;
    }
    """

# Change styles using CSS classes.
another_title_stylesheet = """
:host(.title)  {
    --mono-font: Helvetica;
}
"""


class Scheduler(param.Parameterized):
    
    # TODO: clean up parameters: which parameters actually need to be Parameters?
    
    scheduler_fname = param.String(default="",
                                   label="Scheduler pickle file")
    # scheduler_fname = param.Path(default='scheduler.p', search_paths=['/'])
    date            = param.Date(Time.now().datetime.date())
    # tier            = param.ObjectSelector(default="", objects=[""])
    survey          = param.Integer(default=0)
    basis_function  = param.Integer(default=-1)
    survey_map      = param.ObjectSelector(default="reward", objects=["reward"])
    nside           = param.ObjectSelector(default=16,
                                           objects=[2**n for n in np.arange(1, 6)],
                                           label="Map resolution (nside)")
    color_palette   = param.ObjectSelector(default="Viridis256",
                                           objects=COLOR_PALETTES)

    _data_loaded  = param.Boolean(default=False)    
    _plot_display = param.Integer(default=1)
    _debug_string = param.String(default="")

    _scheduler                = param.Parameter(None)
    _conditions               = param.Parameter(None)
    _date_time                = param.Parameter(None)
    _rewards                  = param.Parameter(None)
    _survey_rewards           = param.Parameter(None)
    _listed_survey            = param.Parameter(None)
    _survey_maps              = param.Parameter(None)
    _tier_survey_rewards      = param.Parameter(None)
    _basis_functions          = param.Parameter(None)
    _survey_df_widget         = param.Parameter(None)
    _basis_function_df_widget = param.Parameter(None)
    _debugging_message        = param.Parameter(None)
    
    # To indicate that data is being loaded
    is_loading = False
    
    _base_sky_map = param.Parameter(None)
    
    create_new_survey_widget = param.Parameter(None)
    
    create_basis_function_widget = param.Parameter(None)
    update_basis_function_widget = param.Parameter(None) 
    
    publish_survey_widget = param.Parameter(None)
    publish_bf_widget = param.Parameter(None)
    publish_map = param.Parameter(None)
    
    tier = param.Parameter(None)
    USER_tier = param.ObjectSelector(default="", objects=[""],label="Tier")
    
    display_basis_function = param.Boolean(default=False)
    update_titles = param.Parameter(None)
    _display_headings = param.Boolean(default=False)
    
    model_observatory = ModelObservatory()
    
    # -------------------------------------------------------------------------
    # ------------------------------------------------------- Dashboard titles

    # TODO: Clean up titles.
    
    # TODO: replace self.survey with first character of survey name (surveys aren't in order in big pickle)
    # TODO: check if being out of order has consequences anywhere else
    
    # Panel for dashboard title.
    def generate_dashboard_title(self):
        
        # if self._scheduler is None or self.tier == '' or self.tier is None:
        if self._display_headings == False:
            return ''
        
        title_string = f'\nTier {self.tier[-1]} - Survey {self.survey}'        # HERE
        
        if self.display_basis_function == False:
            return title_string + ' - Map {}'.format(self.survey_map)
        elif self.display_basis_function == True and self.basis_function >= 0:
            return title_string + ' - Basis function {}'.format(self.basis_function)
        else:
            return title_string
    
    
    @param.depends("update_titles")
    def dashboard_title(self):
        title_string = self.generate_dashboard_title()
        return pn.pane.Str(title_string,
                            height=20,
                            styles={'font-size':'14pt',
                                    'font-weight':'300',
                                    'color':'white'},
                            stylesheets=[title_stylesheet])


    # Panel for survey rewards table title.
    @param.depends("update_titles")
    def survey_rewards_title(self):
        title_string = 'Surveys and rewards'
        if self._display_headings == True and self._scheduler is not None and self.tier != '':
            title_string += ' for tier {}'.format(self.tier[-1])
        survey_rewards_title = pn.pane.Str(title_string,
                                           styles={'font-size':'13pt',
                                                   'font-weight':'300',
                                                   'color':'white'},
                                           stylesheets=[title_stylesheet])
        return survey_rewards_title


    # Panel for basis function table title.
    @param.depends("update_titles")
    def basis_function_table_title(self):  
        title_string = 'Basis functions'
        if self._display_headings==True and self._scheduler is not None:
            title_string += ' for survey {}'.format(self._survey_rewards[self._survey_rewards['tier']==self.tier].reset_index()['survey'][self.survey])
        basis_function_table_title = pn.pane.Str(title_string, 
                                                styles={
                                                    'font-size':'13pt',
                                                    'font-weight':'300',
                                                    'color':'white'},
                                                stylesheets=[another_title_stylesheet], 
                                                css_classes=['title'])
        return basis_function_table_title


    # Panel for map title.
    @param.depends("update_titles")
    def map_title(self):
        if self._display_headings==True and self._scheduler is not None:
            titleA = 'Survey {}\n'.format(self._survey_rewards[self._survey_rewards['tier']==self.tier].reset_index()['survey'][self.survey])
            if self.display_basis_function == False:
                titleB = 'Map: {}'.format(self.survey_map)
            elif self.display_basis_function == True and self.basis_function >= 0:
                titleB = 'Basis function {}: {}'.format(self.basis_function,
                                                        self._basis_functions['basis_func'][self.basis_function])
            else:
                titleB = ''
            title_string = titleA + titleB
        else:
            title_string = 'Map'
        map_title = pn.pane.Str(title_string, 
                                styles={
                                    'font-size':'13pt',
                                    'font-weight':'300',
                                    'color':'white'},
                                stylesheets=[title_stylesheet])
        return map_title
    
    # -------------------------------------------------------------------------
    # ----------------------------------------------------------- User actions
    
    # TODO: Doc strings.
    
    # USER ACTION : enter new filepath
    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler_fname(self):
        
        '''
        start loading spinner
        
        read_scheduler()
        
        update conditions with date
        update scheduler with conditions
        make_reward_df()
        make_scheduler_summary_df()
        apply URL formatting to survey_rewards table
        update tier list with available tiers
        set tier=0, survey=0
        
        filter list of surveys to show tier 0 surveys only
        create survey tabulator widget
        
        compute_maps() for tier 0 survey 0 nside n
        update survey_maps to show maps for tier 0 survey 0
        create sky_map with tier 0 survey 0 reward map
        
        make_survey_reward_df() for tier 0 survey 0
        apply url formatting to basis function table
        create/update basis function tabulator widget
        
        stop loading spinner
        '''
        
        # start loading spinner
        self.is_loading = True
        
        # read_scheduler()
        successful_load = self.read_scheduler()
        
        if successful_load == False:
            self.clear_dashboard()
            self.is_loading = False
            return
        
        # update conditions with date
        # update scheduler with conditions
        # make_reward_df()
        # make_scheduler_summary_df()
        # apply URL formatting to survey_rewards table
        # update tier list with available tiers
        # set tier=0, survey=0
        successful_update = self.make_summary_df()
        
        if successful_update == False:
            self.clear_dashboard()
            self.is_loading = False
            return
        
        self.display_basis_function = False
        
        # filter list of surveys to show tier 0 surveys only
        # self.filter_survey_list()
        # create survey tabulator widget
        self.create_survey_tabulator_widget()
        self.param.trigger("publish_survey_widget")
        
        # compute_maps() for tier 0 survey 0 nside n
        # update survey_maps to show maps for tier 0 survey 0
        self.compute_survey_maps()
        # set survey_map to 'reward'
        self.survey_map = self.param["survey_map"].objects[-1]
        
        self.param.trigger("update_titles")
        
        # create sky_map with tier 0 survey 0 reward map
        self.create_sky_map()
        self.update_sky_map_with_survey_map()
        self.param.trigger("publish_map")
        
        # make_survey_reward_df() for tier 0 survey 0
        # apply url formatting to basis function table
        self.make_survey_reward_dataframe()
        # create/update basis function tabulator widget
        self.create_basis_function_tabulator_widget()
        self.param.trigger("publish_bf_widget")
        
        # stop loading spinner
        self.is_loading = False
        
    
    # USER ACTION : choose date
    @param.depends("date", watch=True)
    def _update_date(self):
        
        '''
        start loading spinner
        
        set datetime to mjd
        
        update conditions with date
        update scheduler with conditions
        make_reward_df()
        make_scheduler_summary_df()
        apply URL formatting to survey_rewards table
        update tier list with available tiers
        set tier=0, survey=0
        
        filter list of surveys to show tier 0 surveys only
        create/update survey tabulator widget
        
        compute_maps() for tier 0 survey 0 nside n
        update survey_maps to show maps for tier 0 survey 0
        create sky_map with tier 0 survey 0 reward map
        
        make_survey_reward_df() for tier t survey s
        apply url formatting to basis function table
        create/update basis function tabulator widget
        
        stop loading spinner
        '''
        
        # start loading spinner
        self.is_loading = True
        
        # set datetime to mjd
        self._date_time = Time(pd.Timestamp(self.date, tzinfo=ZoneInfo('America/Santiago'))).mjd
        
        # update conditions with date
        # update scheduler with conditions
        # make_reward_df()
        # make_scheduler_summary_df()
        # apply URL formatting to survey_rewards table
        # update tier list with available tiers
        # set tier=0, survey=0
        successful_update = self.make_summary_df()
        
        if successful_update == False:
            self.clear_dashboard()
            self.is_loading = False
            return
        
        self.display_basis_function = False
        
        # filter list of surveys to show tier 0 surveys only
        # self.filter_survey_list()
        # create survey tabulator widget
        if self._survey_df_widget is None:
            self.create_survey_tabulator_widget()
        else:
            self.update_survey_tabulator_widget()
        self.param.trigger("publish_survey_widget")
        
        # compute_maps() for tier 0 survey 0 nside n
        # update survey_maps to show maps for tier 0 survey 0
        self.compute_survey_maps()
        # set survey_map to 'reward'
        self.survey_map = self.param["survey_map"].objects[-1]
        
        self.param.trigger("update_titles")
        
        # create sky_map with tier 0 survey 0 reward map
        self.create_sky_map()
        self.update_sky_map_with_survey_map()
        self.param.trigger("publish_map")
        
        # make_survey_reward_df() for tier 0 survey 0
        # apply url formatting to basis function table
        self.make_survey_reward_dataframe()
        # create/update basis function tabulator widget
        self.create_basis_function_tabulator_widget()
        self.param.trigger("publish_bf_widget")

        # stop loading spinner
        self.is_loading = False
    
    
    # USER ACTION : choose tier
    @param.depends("USER_tier", watch=True)
    def _update_tier(self):
        
        '''        
        filter list of surveys to show tier t surveys only
        update survey tabulator widget
        
        compute_maps() for tier t survey 0 nside n
        update survey_maps to show maps for tier t survey 0
        create sky_map with tier t survey 0 reward map
        
        make_survey_reward_df() for tier t survey 0
        apply url formatting to basis function table
        create basis_function_table widget
        '''
        
        if self._display_headings == False:
            return
        
        self.tier = self.USER_tier
        self.survey = 0
        
        self.display_basis_function = False
        
        # filter list of surveys to show tier t surveys only
        # self.filter_survey_list()
        # update survey tabulator widget
        if self._survey_df_widget is None:
            self.create_survey_tabulator_widget()
        else:
            self.update_survey_tabulator_widget()
        self.param.trigger("publish_survey_widget")
        # survey_widget.add_filter()   # can't use - doesn't work
        
        # compute_maps() for tier 0 survey 0 nside n
        # update survey_maps to show maps for tier 0 survey 0
        self.compute_survey_maps()
        # set survey_map to 'reward'
        self.survey_map = self.param["survey_map"].objects[-1]
        
        self.param.trigger("update_titles")
        
        # make_survey_reward_df() for tier t survey 0
        # apply url formatting to basis function table
        self.make_survey_reward_dataframe()
        # create/update basis function tabulator widget
        if self._basis_function_df_widget is None:
            self.create_basis_function_tabulator_widget()
        else:
            self.update_basis_function_tabulator_widget()
        self.param.trigger("publish_bf_widget")
        
        # create sky_map with tier 0 survey 0 reward map
        self.create_sky_map()
        self.update_sky_map_with_survey_map()
        self.param.trigger("publish_map")
        
    
    # USER ACTION : choose survey
    @param.depends("_survey_df_widget.selection", watch=True)
    def _update_survey(self):
        
        '''
        set survey to selection

        compute_maps() for tier t survey s nside n
        update survey_maps to show maps for tier t survey s
        create sky_map with tier t survey s reward map

        make_survey_reward_df() for tier t survey s
        apply url formatting to basis function table
        create/update basis function tabulator widget
        '''
        
        if self._survey_df_widget.selection == []:
            return
        
        # set survey to selection
        self.survey = self._survey_df_widget.selection[0]
        
        self.display_basis_function = False
        
        # compute_maps() for tier t survey s nside n
        # update survey_maps to show maps for tier t survey s
        self.compute_survey_maps()
        # set survey_map to 'reward'
        self.survey_map = self.param["survey_map"].objects[-1]
        
        self.param.trigger("update_titles")
        
        # make_survey_reward_df() for tier t survey s
        # apply url formatting to basis function table
        self.make_survey_reward_dataframe()
        # create/update basis function tabulator widget
        if self._basis_function_df_widget is None:
            self.create_basis_function_tabulator_widget()
        else:
            self.update_basis_function_tabulator_widget()
        self.param.trigger("publish_bf_widget")
        
        # create sky_map with tier t survey s reward map
        self.create_sky_map()
        self.update_sky_map_with_survey_map()
        self.param.trigger("publish_map")
        
    
    # USER ACTION : choose basis function
    @param.depends("_basis_function_df_widget.selection", watch=True)
    def _update_basis_function(self):
        '''
        set basis function to selection
        IF basis function in survey maps list:
            update sky_map with basis function bf
        ELSE:
            ...
            update sky_map with basis function bf
        '''
        
        if self._basis_function_df_widget.selection == []:
            return
        
        # set basis function to selection
        self.basis_function = self._basis_function_df_widget.selection[0]
        
        self.display_basis_function = True
        
        self.param.trigger("update_titles")
        
        # IF basis function in survey maps list:
            # update sky_map with basis function bf
        # ELSE:
            # ...
            # update sky_map with basis function bf
        self.update_sky_map_with_basis_function()
        
        self.param.trigger("publish_map")
        
    
    # USER ACTION - choose map
    @param.depends("survey_map", watch=True)
    def _update_survey_map(self):
        '''
        IF selection is a sky-brightness map or rewards:
            ...
            update sky_map with map selection
        IF selection is a basis-function:
            ...
            update sky_map with map selection
        '''
        
        if self._basis_function_df_widget is not None:
            self._basis_function_df_widget.selection = []
        self.display_basis_function = False
        
        self.param.trigger("update_titles")
        
        # IF selection is a sky-brightness map or rewards:
            # ...
            # update sky_map with map selection
        self.update_sky_map_with_survey_map()
        # ELSE (selection is basis function):
            # ...
            # update sky_map with map selection
        # self.update_sky_map_with_basis_function()
        
        self.param.trigger("publish_map")
        
    
    # USER ACTION - choose nside
    @param.depends("nside", watch=True)
    def _update_nside(self):
        '''
        compute_maps() for tier t survey s nside n
        update survey_maps to show maps for tier t survey s nside n
        create new sky_map with all previous selections and new nside
        '''
        
        if self._display_headings == False:
            return
        
        # compute_maps() for tier t survey s nside n
        # update survey_maps to show maps for tier t survey s nside n
        self.compute_survey_maps()
        
        # create new sky_map with all previous selections and new nside
        self.create_sky_map()
        self.update_sky_map_with_survey_map()
        self.param.trigger("publish_map")
        
    
    # USER ACTION - choose color palette
    @param.depends("color_palette", watch=True)
    def _update_color_palette(self):
        '''
        update sky_map with color palette selection
        '''
        # update sky_map with color palette selection
        # IF current selection is survey_map:
        self.update_sky_map_with_survey_map()
        # ELSE (selection is basis function):
        # self.update_sky_map_with_basis_function()
        
        self.param.trigger("publish_map")
        
        
    # -------------------------------------------------------------------------
    # ------------------------------------------------------ Internal workings
    
    
    def clear_dashboard(self):
        
        self._survey_df_widget = None
        self.param.trigger("publish_survey_widget")
        
        self._basis_functions = None
        self.param.trigger("publish_bf_widget")
        
        self._base_sky_map = None
        self.param.trigger("publish_map")
        
        self._display_headings = False
        self.param.trigger("update_titles")
        
        self.param["USER_tier"].objects = [""]
        self.param["survey_map"].objects = [""]
        
        self.USER_tier = ""        
        self.tier = ""
        self.survey_map = ""
        
        self.survey = 0
        self.basis_function = -1
        
        
    def read_scheduler(self):
        
        try:
            pn.state.notifications.info("Scheduler loading...", 0)
            logging.info("Reading scheduler and conditions.")
            
            (scheduler, conditions) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)
            self._scheduler = scheduler
            self._conditions = conditions
            
            pn.state.notifications.clear()
            pn.state.notifications.success("Scheduler pickle loaded successfully!")
            
            return True
        
        except:
            logging.error(f"Could not load scheduler from {self.scheduler_fname} \n{traceback.format_exc(limit=-1)}")
            pn.state.notifications.clear()
            pn.state.notifications.error(f"Could not load scheduler from {self.scheduler_fname}", 0)
            
            self._scheduler = None
            self._conditions = None
            self._display_headings = False
            
            return False
    
    
    def make_summary_df(self):
        
        if self._scheduler is None:
            logging.info("Cannot update survey reward table as no pickle is loaded.")
            return False
        
        try:
            pn.state.notifications.info("Making scheduler summary dataframe...", duration=0)
            logging.info("Making scheduler summary dataframe.")
            
            # TEMPORARY BUG-FIX.
            # self._conditions.mjd = self._date_time
            # self._conditions.__dict__.clear()
            # self._conditions.__dict__.update(model_observatory.return_conditions().__dict__)
            if self.model_observatory.nside != self._scheduler.nside:
                self.model_observatory = ModelObservatory(nside=self._scheduler.nside)
            self.model_observatory.mjd = self._date_time
            self._conditions = self.model_observatory.return_conditions()
            
            self._scheduler.update_conditions(self._conditions)
            self._rewards  = self._scheduler.make_reward_df(self._conditions)
            survey_rewards = schedview.compute.scheduler.make_scheduler_summary_df(
                self._scheduler,
                self._conditions,
                self._rewards,
                )
            
            # Duplicate column and apply URL formatting to one of the columns.
            survey_rewards['survey'] = survey_rewards.loc[:, 'survey_name']
            survey_rewards['survey_name'] = survey_rewards.apply(survey_url_formatter, axis=1)            
            self._survey_rewards = survey_rewards
            
            # Update tier list
            tiers = self._survey_rewards.tier.unique().tolist()
            # self.param["tier"].objects = tiers
            self.param["USER_tier"].objects = tiers
            # TODO: set self.USER_tier = tiers[0] without triggering _update_tier()
            self.tier = tiers[0]
            
            self.survey = 0
            
            self._display_headings = True
            
            pn.state.notifications.clear()
            pn.state.notifications.success("Scheduler summary dataframe updated successfully")
            
            return True
            
        except:
            logging.info(f"Scheduler summary dataframe unable to be updated: \n{traceback.format_exc(limit=-1)}")      
            pn.state.notifications.clear()
            pn.state.notifications.error("Scheduler summary dataframe unable to be updated!", duration=0)
            self._survey_rewards = None
            
            return False
    
    
    def create_survey_tabulator_widget(self):
        
        if self._survey_rewards is None:
            return
        
        logging.info("Creating survey widget.")
        
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
            self._survey_rewards[self._survey_rewards['tier']==self.tier][columns],
            widths={'survey_name':'60%','reward':'40%'},
            show_index=False,
            formatters=tabulator_formatter,
            titles=titles,
            disabled=True,
            selectable=1,
            hidden_columns=['tier','survey','survey_url'],
            pagination='remote',
            page_size=4,
            sizing_mode='stretch_width',
            )
        
        self._survey_df_widget = survey_rewards_table
        
    
    def update_survey_tabulator_widget(self):
        
        logging.info("Updating survey widget.")
        
        # update data for widget
        columns = [
            'tier',
            'survey_name',
            'reward',
            'survey',
            'survey_url',
            ]
        
        self._survey_df_widget._update_data(self._survey_rewards[self._survey_rewards['tier']==self.tier][columns])
    
    
    @param.depends("publish_survey_widget")
    def publish_survey_tabulator_widget(self):
        
        if self._survey_df_widget is None:
            return "No surveys available."
        
        else:
            return self._survey_df_widget
    
    
    def compute_survey_maps(self):
        
        if self._scheduler is None:
            logging.info("Cannot compute survey maps as no scheduler loaded.")
            return
        
        if self._survey_rewards is None:
            logging.info("Cannot compute survey maps as no scheduler summary made.")
            return
        
        try:
            logging.info("Computing survey maps.")
            
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            
            self._listed_survey = self._scheduler.survey_lists[tier_id][survey_id]
            
            self._survey_maps = schedview.compute.survey.compute_maps(
                self._listed_survey,
                self._conditions,
                self.nside,
                )
            
            self.param["survey_map"].objects = list(self._survey_maps.keys())
                        
        except:
            logging.info(f"Cannot compute survey maps: \n{traceback.format_exc(limit=-1)}")
    
    
    def make_survey_reward_dataframe(self):
        
        if self._scheduler is None:
            logging.info("Cannot make survey reward dataframe as no scheduler loaded.")
            return
        
        if self._survey_rewards is None:
            logging.info("Cannot make survey reward dataframe as no scheduler summary made.")
            return
        
        try:
            logging.info("Making survey reward dataframe.")
            
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            
            # Check that survey has basis functions.
            if self._rewards.index.isin([(tier_id, survey_id)]).any():
                
                # Create dataframe.
                basis_function_df = schedview.compute.survey.make_survey_reward_df(
                    self._listed_survey,
                    self._conditions,
                    self._rewards.loc[[(tier_id, survey_id)], :]
                    )
                # Duplicate column and apply URL formatting to one of the columns.
                basis_function_df['basis_func'] = basis_function_df.loc[:, 'basis_function']
                basis_function_df['basis_function'] = basis_function_df.apply(basis_function_url_formatter, axis=1)
                self._basis_functions = basis_function_df
            else:
                self._basis_functions = None
        
        except:
            logging.info(f"Cannot make survey reward dataframe: \n{traceback.format_exc(limit=-1)}")
    
    
    def create_basis_function_tabulator_widget(self):
        
        if self._basis_functions is None:
            return
        
        logging.info("Creating basis function widget.")
        
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
            layout="fit_data",
            show_index=False,
            formatters=tabulator_formatter,
            disabled=True,
            frozen_columns=['basis_function'],
            hidden_columns=['basis_func','doc_url'],
            selectable=1,
            pagination='remote',
            page_size=13
            )
        
        self._basis_function_df_widget = basis_function_table

    
    def update_basis_function_tabulator_widget(self):
        
        if self._basis_functions is None:
            return
        
        # reset selection
        self._basis_function_df_widget.selection = []
        
        logging.info("Updating basis function widget.")
        
        # update data for widget
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
    
    
    @param.depends("publish_bf_widget")
    def publish_basis_function_widget(self):
        
        if self._basis_functions is None:
            return "No basis functions available."
        
        else:
            return self._basis_function_df_widget
        
    
    def create_sky_map(self):
        
        if self._survey_maps is None:
            logging.info("Cannot create sky map as no survey maps made.")
            return
        
        try:
            logging.info("Creating sky map.")
            
            # Make a dummy map that is 1.0 for all healpixels that might have data.
            self._survey_maps['above_horizon'] = np.where(self._conditions.alt > 0, 1.0, np.nan)
            
            # Make the map figure for the new survey data.
            self._base_sky_map = schedview.plot.survey.map_survey_healpix(
                self._conditions.mjd,
                self._survey_maps,
                'above_horizon',
                self.nside,
                )
            # Remove 'above_horizon' from tooltip.
            self._base_sky_map.plot.toolbar.tools[-1].tooltips.remove(('above_horizon', '@above_horizon'))
            
        except:
            logging.info(f"Cannot create sky map: \n{traceback.format_exc(limit=-1)}")
    
    
    def update_sky_map_with_survey_map(self):
        
        if self._base_sky_map is None:
            "Cannot update sky map with survey map as no base map loaded."
            return
        
        logging.info("Updating sky map with survey map.")
        
        # Update figure to show a different map by modifying the existing bokeh objects and pushing update.
        hpix_renderer = self._base_sky_map.plot.select(name="hpix_renderer")[0]
        hpix_data_source = self._base_sky_map.plot.select(name="hpix_ds")[0]
        
        # If selection is a basis function
        if self.survey_map not in ['u_sky', 'g_sky', 'r_sky', 'i_sky', 'z_sky', 'y_sky', 'reward']:
            
            logging.info("CASE 1")
            
            bf = self.survey_map.split('@')[0].strip()
            bf_underscored = bf.replace(" ", "_")
            bf_survey_key = list(key for key in self._survey_maps.keys() if bf in key)[0]
            bf_bokeh_key = list(key for key in hpix_data_source.data.keys() if bf_underscored in key)[0]
            
            # Get range of values.
            min_good_value = np.nanmin(self._survey_maps[bf_survey_key])
            max_good_value = np.nanmax(self._survey_maps[bf_survey_key])
            
            if min_good_value == max_good_value:
                min_good_value -= 1
                max_good_value += 1
            
            logging.info(f"(min,max): ({min_good_value},{max_good_value})")
            self._debugging_message = f"(min,max): ({min_good_value},{max_good_value})"
            
            hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                field_name=bf_bokeh_key,
                palette=self.color_palette,
                low=min_good_value,
                high=max_good_value,
                nan_color='white'
                )
        
        # If survey map is all NaNs.
        elif np.isnan(self._survey_maps[self.survey_map]).all():
            
            logging.info("CASE 2")
            
            hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                field_name=self.survey_map,
                palette=self.color_palette,
                low=-1,
                high=1,
                nan_color='white'
                )
            
        # CASE 2: If survey map is not all NaNs.
        else:
            logging.info("CASE 3")
            
            # Get range of values.
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
                nan_color='white'
                )
            
        hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
            
        # Update map.
        self._base_sky_map.update()
            
            
    def update_sky_map_with_basis_function(self):
        
        if self._base_sky_map is None:
            "Cannot update sky map with basis function as no base map loaded."
            return
        
        try:
            
            logging.info("Updating sky map with basis function.")
            
            # Update figure to show a different map by modifying the existing bokeh objects and pushing update.
            hpix_renderer = self._base_sky_map.plot.select(name="hpix_renderer")[0]
            hpix_data_source = self._base_sky_map.plot.select(name="hpix_ds")[0]
            
            # Get name of basis function.
            bf = self._basis_functions['basis_func'][self.basis_function]
            bf_underscored = bf.replace(" ", "_")
            
            # -------------------------------------------------------------
            # CASE 4: If basis function IS in the list of survey maps (it is scalar)
            if any(bf in key for key in self._survey_maps.keys()):
                
                logging.info("CASE 4")
                
                # Get keys.            
                bf_survey_key = list(key for key in self._survey_maps.keys() if bf in key)[0]
                bf_bokeh_key = list(key for key in hpix_data_source.data.keys() if bf_underscored in key)[0]
                
                # Get range of values.
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
                    nan_color='white'
                    )
                
            # -------------------------------------------------------------
            # CASE 5: If basis function is NOT in list of survey maps
            # (i.e. it is scalar and hasn't yet been selected and added to survey maps).
            else:
                
                # Create array populated with scalar values where sky brightness map is not NaN.
                scalar_array = hpix_data_source.data['u_sky'].copy() 
                
                # Get max_basis_reward.
                max_basis_reward = self._basis_functions.loc[self.basis_function,:]['max_basis_reward']
                
                # If max_basis_reward is finite.
                if max_basis_reward != -np.inf:
                    
                    logging.info("CASE 5")
                    
                    # Create array populated with scalar values where sky brightness map is not NaN.
                    scalar_array[~np.isnan(hpix_data_source.data['u_sky'])] = self._basis_functions.loc[self.basis_function,:]['max_basis_reward']
                    
                    hpix_data_source.data[bf_underscored] = scalar_array
                    hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                        field_name=bf_underscored,
                        palette=self.color_palette,
                        low=max_basis_reward-1,
                        high=max_basis_reward+1,
                        nan_color='white'
                        )
                    
                    # Add to tooltip.
                    at_bf = f"@{bf_underscored}"
                    self._base_sky_map.plot.toolbar.tools[-1].tooltips.append((bf, at_bf))

                
                # TODO: Does this case ever occur? Yes, tier 1. Map is blank.
                
                # If max_basis_reward is -inf.
                else:
                    
                    logging.info("CASE 6")
                    
                    # Create array populated with -1 where sky brightness map is not NaN.
                    scalar_array[~np.isnan(hpix_data_source.data['u_sky'])] = -1
                    
                    # TODO: Check on tooltips: when are they added? When are they duplicated?
                    
                    # Add new key-pair (basis_function: scalar array) to survey_maps dictionary.
                    # self._survey_maps[self._basis_functions['basis_func'][self.basis_function]] = scalar_array
                    
                    hpix_renderer.glyph.fill_color = bokeh.transform.linear_cmap(
                        field_name=self._basis_functions['basis_func'][self.basis_function],
                        palette="Greys256",
                        low=-2,
                        high=0,
                        nan_color='magenta'
                        )
                
            hpix_renderer.glyph.line_color = hpix_renderer.glyph.fill_color
            
            # Update map.
            self._base_sky_map.update()
            
        except:
            logging.info(f"Could not load map: \n{traceback.format_exc(limit=-1)}")


    @param.depends("publish_map")
    def publish_sky_map(self):
        
        if self._conditions is None:
            return "No scheduler loaded."
        
        elif self._survey_maps is None:
            return "No surveys are loaded."
        
        elif self._base_sky_map is None:
            return "No map loaded."
        
        else:
            logging.info("Publishing sky map.")
            return self._base_sky_map.figure
    
    
    # -------------------------------------------------------------------------
    # -------------------------------------------------------- Debugging panel


    @param.depends("_debugging_message")
    def debugging_messages(self):
        if self._debugging_message is None:
            return
        timestamp = datetime.now(timezone('America/Santiago')).strftime('%Y-%m-%d %H:%M:%S')
        self._debug_string = f"\n {timestamp} - {self._debugging_message}" + self._debug_string
        debugging_messages = pn.pane.Str(self._debug_string,
                                         height=70,
                                         styles={'font-size':'9pt',
                                                 'color':'black',
                                                 'overflow': 'scroll'})
        return debugging_messages


    # -------------------------------------------------------------------------
    # ------------------------------------------------- Page loading indicator
    
    
    @param.depends('is_loading', watch=True)
    def update_loading(self):
        sched_app.loading = self.is_loading


# -----------------------------------------------------------------------------
# ------------------------------------------------------------------------ Key


def generate_array_for_key(number_of_columns=4):
    
    return {
        # x,y coordinates for glyphs (lines, circles and text).
        "x_title"   : np.array([7]),    # Title x coord
        "y_title"   : np.array([5.75]), # Title y coord
        "x_circles" : np.tile(8,number_of_columns),     # Circle centre coords
        "x_text_1"  : np.tile(2.5,number_of_columns),   # Text in colunn 1
        "x_text_2"  : np.tile(8.75,number_of_columns),  # Text in column 2
        "x0_lines"  : np.tile(0.75,number_of_columns),  # Start lines
        "x1_lines"  : np.tile(2,number_of_columns),     # End lines
        "y" : np.arange(number_of_columns,0,-1),        # y coords for all items except title

        # Colours and sizes of images.
        "line_colours"   : np.array(['black','red','#1f8f20','#110cff']),
        "circle_colours" : np.array(['#ffa500','grey','red','#1f8f20']),
        "circle_sizes"   : np.tile(10,number_of_columns),
        
        # Text for title and key items.
        "title_text" : np.array(['Key']),
        "text_1"     : np.array(['Horizon','ZD=70 degrees','Ecliptic','Galactic plane']),                 # Column 1
        "text_2"     : np.array(['Sun position','Moon position','Survey field(s)','Telescope pointing']), # Column 2
        }

# Generates the key as a Bokeh plot.
def generate_key():
    
    data_array = generate_array_for_key()
    
    # Assign above data to relevant data source (to be used in glyph creation below).
    title_source  = bokeh.models.ColumnDataSource(dict(x=data_array["x_title"], y=data_array["y_title"], text=data_array["title_text"]))
    text1_source  = bokeh.models.ColumnDataSource(dict(x=data_array["x_text_1"], y=data_array["y"], text=data_array["text_1"]))
    text2_source  = bokeh.models.ColumnDataSource(dict(x=data_array["x_text_2"], y=data_array["y"], text=data_array["text_2"]))
    circle_source = bokeh.models.ColumnDataSource(dict(x=data_array["x_circles"], y=data_array["y"], sizes=data_array["circle_sizes"], colours=data_array["circle_colours"]))
    line_source   = bokeh.models.ColumnDataSource(dict(x0=data_array["x0_lines"], y0=data_array["y"], x1=data_array["x1_lines"],y1=data_array["y"], colours=data_array["line_colours"]))

    # Create glyphs.
    border_glyph = bokeh.models.Rect(x=7, y=3.25, width=14, height=6.5, line_color="#048b8c", fill_color=None, line_width=3)
    header_glyph = bokeh.models.Rect(x=7, y=5.75, width=14, height=1.5, line_color=None,      fill_color="#048b8c")
    title_glyph  = bokeh.models.Text(x='x', y='y', text='text', text_font_size='15px', text_color='white', text_baseline='middle', text_font = {'value': 'verdana'}, text_align='center')#, text_font_style='bold'
    text1_glyph  = bokeh.models.Text(x="x", y="y", text="text", text_font_size='10px', text_color="black", text_baseline='middle', text_font = {'value': 'verdana'})
    text2_glyph  = bokeh.models.Text(x="x", y="y", text="text", text_font_size='10px', text_color="black", text_baseline='middle', text_font = {'value': 'verdana'})
    circle_glyph = bokeh.models.Circle(x="x", y="y", size="sizes", line_color="colours", fill_color="colours")
    line_glyph   = bokeh.models.Segment(x0="x0", y0="y0", x1="x1", y1="y1", line_color="colours", line_width=2, line_cap='round')
    
    # Create plot.
    key = bokeh.models.Plot(title=None, width=300, height=150, min_border=0, toolbar_location=None)

    # Add glyphs to plot.
    key.add_glyph(border_glyph)
    key.add_glyph(header_glyph)
    key.add_glyph(title_source,  title_glyph)
    key.add_glyph(text1_source,  text1_glyph)
    key.add_glyph(text2_source,  text2_glyph)
    key.add_glyph(circle_source, circle_glyph)
    key.add_glyph(line_source,   line_glyph)
    
    return key

# -----------------------------------------------------------------------------

# Moved app pane outside scheduler_app so that it is accessible from Scheduler class.
sched_app = pn.GridSpec(sizing_mode='stretch_both', max_height=1000).servable()


def scheduler_app(date=None, scheduler_pickle=None):
    
    scheduler = Scheduler()
    
    if date is not None:
        scheduler.date = date
    
    if scheduler_pickle is not None:
        scheduler.scheduler_fname = scheduler_pickle
    
    # Dashboard title.
    sched_app[0:8, :]        = pn.Row(pn.Column(pn.Spacer(height=4),
                                                pn.pane.Str('Scheduler Dashboard',
                                                            height=20,
                                                            styles={'font-size':'16pt',
                                                                    'font-weight':'500',
                                                                    'color':'white'},
                                                            stylesheets=[title_stylesheet]),
                                                scheduler.dashboard_title),
                                      pn.layout.HSpacer(),
                                      pn.pane.PNG(LOGO,
                                                  sizing_mode='scale_height',
                                                  align='center', margin=(5,5,5,5)),
                                      sizing_mode='stretch_width',
                                      styles={'background':'#048b8c'})
    # Parameter inputs (pickle, date, tier)
    sched_app[8:33, 0:21]    = pn.Param(scheduler,
                                        parameters=["scheduler_fname","date","USER_tier"],
                                        widgets={'scheduler_fname':{'widget_type':pn.widgets.TextInput,
                                                                    'placeholder':'filepath or URL of pickle'},
                                                 'date':pn.widgets.DatetimePicker},
                                        name="Select pickle file, date and tier.")
    # Survey rewards table and header.
    sched_app[8:33, 21:67]   = pn.Row(pn.Spacer(width=10),
                                      pn.Column(pn.Spacer(height=10),
                                                pn.Row(scheduler.survey_rewards_title,
                                                       styles={'background':'#048b8c'}),
                                                pn.param.ParamMethod(scheduler.publish_survey_tabulator_widget, loading_indicator=True)),
                                      pn.Spacer(width=10),
                                      sizing_mode='stretch_height')
    # Basis function table and header.
    sched_app[33:87, 0:67]   = pn.Row(pn.Spacer(width=10),
                                      pn.Column(pn.Spacer(height=10),
                                                pn.Row(scheduler.basis_function_table_title,
                                                       styles={'background':'#048b8c'}),
                                                pn.param.ParamMethod(scheduler.publish_basis_function_widget, loading_indicator=True)),
                                      pn.Spacer(width=10))
    # Map display and header.
    sched_app[8:59, 67:100]  = pn.Column(pn.Spacer(height=10),
                                         pn.Row(scheduler.map_title,styles={'background':'#048b8c'}),
                                         pn.param.ParamMethod(scheduler.publish_sky_map, loading_indicator=True))
    # Bokeh plot key.
    sched_app[66:87, 67:87] = pn.Column(pn.Spacer(height=32),
                                        pn.pane.Bokeh(generate_key()))
    # Map display parameters (map, nside, color palette).
    sched_app[66:87, 87:100] = pn.Param(scheduler,
                                        parameters=["survey_map","nside","color_palette"],
                                        show_name=False)
    # Debugging collapsable card.
    sched_app[87:100, :]     = pn.Card(pn.Column(scheduler.debugging_messages,
                                                 styles={'background':'#EDEDED'}),
                                       title='Debugging',
                                       header_background='white',
                                       styles={'background':'#048b8c'},
                                       sizing_mode='stretch_width',
                                       collapsed=True)
    
    ### -----------------------------------------------------------------------

    return sched_app

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting scheduler dashboard.")

    if "SCHEDULER_PORT" in os.environ:
        scheduler_port = int(os.environ["SCHEDULER_PORT"])
    else:
        scheduler_port = 8080

    pn.serve(
        scheduler_app,
        port       = scheduler_port,
        title      = "Scheduler Dashboard",
        show       = True,
        start      = True,
        autoreload = True,
        threaded   = True,
        static_dirs = {'assets': './assets'}
    )