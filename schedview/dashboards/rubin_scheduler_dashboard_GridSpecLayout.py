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

# Packages required for debugging timestamp option 3
# from datetime import datetime
# from astropy.time import Time, TimezoneInfo
# import astropy.units as u

import schedview
import schedview.compute.scheduler
import schedview.compute.survey
import schedview.collect.scheduler_pickle
import schedview.plot.survey


"""
Notes
-----
    
    - Syntax, naming conventions, formatting, etc., mostly follows Eric's
      prenight.py.


Still to implement
------------------
    
    Loading indicator/floating error message:
    
        1. Loading indicator when new pickle/datetime chosen.
            - https://panel.holoviz.org/reference/global/Notifications.html
            - pn.extension(notifications=True)
              pn.state.notifications.info('Pickle file loading.', duration=0)
        2. Floating error message appear when bad/invalid pickle or invalid date.
            - The pop-up should be triggered by watching the error messages
              that are sent to debugging and checking for errors of interest.
            - Which errors should cause a pop-up?
                - "Invalid pickle - perhaps try another?"
                - "Can't access the pickle - are you sure you have the right file?"
                - "Invalid date - perhaps date out of range for this pickle?"
                - ...
    
    Load big pickle/URL pickle:
    
        1. Check if able to load pickle from a URL.
        2. Check how dashboard handles large pickle (many surveys).
    
    URL:
        
        - Accept parameters (pickle file url, mjd, survey, nside) in the url
          so other dashboards can link to it in a given state.


Further potential modifications
-------------------------------

    1. [efficient code]  Find duplicate code sections and replace with methods, where sensible.
    2. [clean code]  Clean up sky_map().
    3. [product polish]     Populate with useful messages sent to debugger.
    4. [product polish]     Bokeh key degree symbol
        - convert all Text objects to Label objects to use LaTeX.
    5. [code style]  Change all parameter lists to have their closing bracket on a new line.


Current issues/quirks
---------------------

    Blank map:
        
        - SolarElongationMask (tier 4 surveys) shows blank map because basis_area=0
          (even though healpix array is not all -inf values. 25%=1)
        - Blank map also means no tooltip.
        - I currently send a message to debugging noting the map is empty due to
          basis_area. Is this behaviour okay? (Blank map, no tooltip, messsage).
        - Should we treat such a case differently?
    
    Deserialisation error:
        
         - A deserialisation error keeps appearing (and appears very frequently
           when the Bokeh key is shown). It clogs up the command line to the
           extent that it becomes unreadable.
         - ERROR:bokeh.server.protocol_handler:error handling message error:
           DeserializationError("can't resolve reference 'p6667'")
         - Apparently this error/warning has been changed to something less
           intense with Bokeh 3.2.
    
    Survey_map selection:
        
        - When a non-scalar basis function is selected from the table, perhaps
          the survey_map drop-down selector should change to reflect this?
        - When a scalar basis function is selected, perhaps we should show a
          blank selection?
    
    Basis function table:
        
        - The column headers make the table wider than can fit in space.
        - Can we remove the sorting arrows to reduce width of each column?
        - Javascript: {title:"Name", field:"name", sorter:"string", headerSort:false} 


Pending questions
-----------------
    
    - Can we remove sorting arrows in basis_function table headers to reduce
      column widths?
    - Do they still want a colour scale for the plot or is the tooltip info
      enough?
    - How about the latest debugging collapsable card? Can we keep it?
    - What kinds of messages should be shown in debugging panel?
        - Only errors/unsuccessful updates?
        - "Updating ...", "Successfully updated.", "Could not update ..."
    - Do they want to distinguish between -inf (infesible) vs -nan (feasible)
          - using different colours, i.e. two different greys?
    - Should scalar maps that return finite values be a colour or is grey okay?
    - Is the moon coloured orange instead of the sun? (check out MoonAvoidance)
    

"""

color_palettes = [s for s in bokeh.palettes.__palettes__ if "256" in s]

LOGO      = "/assets/lsst_white_logo.png"
#key_image = "/assets/key_image.png"                                            # Not needed if using Bokeh key.

pn.extension("tabulator",
             # css_files   = [pn.io.resources.CSS_URLS["font-awesome"]],
             sizing_mode = "stretch_width",)

logging.basicConfig(format = "%(asctime)s %(message)s",
                    level  = logging.INFO)

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


# Change styles using css variables
title_stylesheet = """
    :host {
        --mono-font: Helvetica;
    }
    """

# Change styles using css classes
another_title_stylesheet = """
:host(.title)  {
    --mono-font: Helvetica;
}
"""


class Scheduler(param.Parameterized):
    
    scheduler_fname = param.String(default="",
                                   label="Scheduler pickle file")
    date            = param.Date(Time.now().datetime.date())
    tier            = param.ObjectSelector(default="", objects=[""])
    survey          = param.Integer(default=-1)
    basis_function  = param.Integer(default=-1)
    survey_map      = param.ObjectSelector(default="", objects=[""])
    plot_display    = param.Integer(default=1)                                 # 1: map, 2: basis function
    nside           = param.ObjectSelector(default=16,
                                           objects=[2**n for n in np.arange(1, 6)],
                                           label="Map resolution (nside)")
    color_palette   = param.ObjectSelector(default="Viridis256",
                                           objects=color_palettes)
    debug_string    = param.String(default="")

    _scheduler                = param.Parameter(None)
    _conditions               = param.Parameter(None)
    _date_time                = param.Parameter(None)
    _rewards                  = param.Parameter(None)                          # not used in @depends method
    _survey_rewards           = param.Parameter(None)
    _listed_survey            = param.Parameter(None)
    _survey_maps              = param.Parameter(None)
    _tier_survey_rewards      = param.Parameter(None)
    _basis_functions          = param.Parameter(None)
    _survey_df_widget         = param.Parameter(None)
    _basis_function_df_widget = param.Parameter(None)
    _debugging_message        = param.Parameter(None)
    
    _data_loaded = param.Boolean(default=False)
    
    # Dashboard headings ------------------------------------------------------# Should these functions be below others?
    
    # Panel for dashboard title.
    @param.depends("tier", "survey", "plot_display", "survey_map", "basis_function")
    def dashboard_title(self):
        titleT  = ''; titleS  = ''; titleBF = ''; titleM = ''
        if self._scheduler is not None:
            if self.tier != '':
                titleT = '\nTier {}'.format(self.tier[-1])
                if self.survey >= 0:
                    titleS = ' - Survey {}'.format(self.survey)
                    if self.plot_display == 1:
                        titleM = ' - Map {}'.format(self.survey_map)
                    elif self.plot_display == 2 and self.basis_function >= 0:
                        titleBF = ' - Basis function {}'.format(self.basis_function)
        title_string = titleT + titleS + titleBF + titleM
        dashboard_title = pn.pane.Str(title_string,
                                      height=20,
                                      styles={'font-size':'14pt',
                                              'font-weight':'300',
                                              'color':'white'},
                                      stylesheets=[title_stylesheet])
        return dashboard_title


    # Panel for survey rewards table title.
    @param.depends("_data_loaded", "tier")
    def survey_rewards_title(self):
        title_string = 'Surveys and rewards'
        if self._data_loaded == True and self._scheduler is not None and self.tier != '':
            title_string += ' for tier {}'.format(self.tier[-1])
        
        survey_rewards_title = pn.pane.Str(title_string,
                                           styles={'font-size':'13pt',
                                                   'font-weight':'300',
                                                   'color':'white'},
                                           stylesheets=[title_stylesheet])
        return survey_rewards_title


    # Panel for basis function table title.
    @param.depends("_data_loaded", "survey")
    def basis_function_table_title(self):  
        title_string = 'Basis functions'
        if self._data_loaded==True and self._scheduler is not None and self.survey >= 0:
            title_string += ' for survey {}'.format(self._tier_survey_rewards.reset_index()['survey'][self.survey])
        
        basis_function_table_title = pn.pane.Str(title_string, 
                                                styles={
                                                    'font-size':'13pt',
                                                    'font-weight':'300',
                                                    'color':'white'},
                                                stylesheets=[another_title_stylesheet], 
                                                css_classes=['title'])
        return basis_function_table_title


    # Panel for map title.
    @param.depends("_data_loaded", "tier", "survey", "plot_display", "survey_map", "basis_function")
    def map_title(self):
        if self._data_loaded==True and self._scheduler is not None and self.survey >= 0:
            titleA = 'Survey {}\n'.format(self._tier_survey_rewards.reset_index()['survey'][self.survey])
            if self.plot_display == 1:
                titleB = 'Map: {}'.format(self.survey_map)
            elif self.plot_display == 2 and self.basis_function >= 0:
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

    
    # Widgets and updates -----------------------------------------------------
    
    
    # Update scheduler if given new pickle file.
    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler(self):
        logging.info("Updating scheduler.")
        try:
            (scheduler, conditions) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)
            self._data_loaded = True
            self._scheduler = scheduler
            self._conditions = conditions
        except:
            logging.error(f"Could not load scheduler from {self.scheduler_fname} \n{traceback.format_exc(limit=-1)}")
            self._debugging_message = f"Could not load scheduler from {self.scheduler_fname}: \n{traceback.format_exc(limit=-1)}"
            self._data_loaded = False
            self._scheduler = None
            self._conditions = None
            self._survey_rewards = None   # -> tier=""             -> _tier_survey_rewards=None
            self.survey = -1              # -> _listed_survey=None -> _survey_maps=None
            self._basis_functions = None
            self.basis_function = -1
            
            # self.param.set_param(_data_loaded= False,
            #                      _scheduler = None,
            #                      _conditions = None,
            #                      _survey_rewards = None,
            #                      survey = -1,
            #                      )
            
            # self.param.set_param(basis_function = -1,
            #                      tier = "",
            #                      )
            
    
    # Update datetime if new datetime chosen.
    @param.depends("date", watch=True)
    def _update_date_time(self):
        logging.info("Updating date.")
        self._date_time = Time(pd.Timestamp(self.date, tzinfo=ZoneInfo('America/Santiago'))).mjd
        logging.info("Date updated to {}".format(self._date_time))
    
    
    # Update survey reward dataframe if given new pickle file or new date.
    # @param.depends("_scheduler", "_conditions", "_date_time", watch=True)
    @param.depends("_conditions", "_date_time", watch=True)
    def _update_survey_rewards(self):
        if self._scheduler is None:
            logging.info("Can not update survey reward table as no pickle is loaded.")
            return
        try:
            logging.info("Updating survey rewards.")
            self._conditions.mjd = self._date_time
            self._scheduler.update_conditions(self._conditions)
            self._rewards  = self._scheduler.make_reward_df(self._conditions)
            survey_rewards = schedview.compute.scheduler.make_scheduler_summary_df(self._scheduler,
                                                                                   self._conditions,
                                                                                   self._rewards)
            # Duplicate column and apply URL formatting to one of the columns.
            survey_rewards['survey'] = survey_rewards.loc[:, 'survey_name']
            survey_rewards['survey_name'] = survey_rewards.apply(survey_url_formatter, axis=1)
            self._survey_rewards = survey_rewards
            self._data_loaded = True
        except:           
            logging.info(f"Survey rewards dataframe unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self._debugging_message = f"Survey rewards dataframe unable to be updated: \n{traceback.format_exc(limit=-1)}"
            self._data_loaded = False
            self._survey_rewards = None
            self._basis_functions = None
            

    # Update available tier selections if given new pickle file.
    @param.depends("_survey_rewards", watch=True)
    def _update_tier_selector(self):
        logging.info("Updating tier selector.")
        if self._survey_rewards is None:
            self.param["tier"].objects = [""]
            self.tier = ""
            return
        tiers = self._survey_rewards.tier.unique().tolist()
        self.param["tier"].objects = tiers
        self.tier = tiers[0]


    # Update (filter) survey list based on tier selection.
    @param.depends("tier", watch=True)
    def _update_survey_reward_table(self):
        if self._survey_rewards is None:
            self._tier_survey_rewards = None
            return
        try:
            logging.info("Updating survey rewards for chosen tier.")
            self._tier_survey_rewards = self._survey_rewards[self._survey_rewards['tier']==self.tier]
            self.survey = 0
        except:
            self._debugging_message = f"Survey rewards unable to be updated: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Survey rewards unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self._tier_survey_rewards = None
            self.survey = -1


    # Widget for survey reward table.
    @param.depends("_tier_survey_rewards")
    def survey_rewards_table(self):
        if self._tier_survey_rewards is None:
            return "No surveys available."
        tabulator_formatter = {'survey_name': HTMLTemplateFormatter(template='<%= value %>')}
        titles = {
            'survey_name': 'Survey Name',
            'reward': 'Reward'
        }
        survey_rewards_table = pn.widgets.Tabulator(self._tier_survey_rewards[['tier','survey_name','reward','survey','survey_url']],
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
        logging.info("Finished updating survey rewards table.")
        self._survey_df_widget = survey_rewards_table
        return survey_rewards_table


    # Update selected survey based on row selection of survey_rewards_table.
    @param.depends("_survey_df_widget.selection", watch=True)
    def _update_survey_with_row_selection(self):
        if self._survey_df_widget.selection == []:
            # self.survey = -1
            return
        try:
            logging.info("Updating survey row selection.")
            self.survey = self._survey_df_widget.selection[0]
        except:
            self._debugging_message = f"Survey selection unable to be updated: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Survey selection unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self.survey = -1
    
    
    # Update listed_survey if tier or survey selections change.
    @param.depends("survey", "tier", watch=True)
    def _update_listed_survey(self):
        logging.info("Updating listed survey.")
        try:
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            self._listed_survey = self._scheduler.survey_lists[tier_id][survey_id]
        except:
            self._debugging_message = f"Listed survey unable to be updated: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Listed survey unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self._listed_survey = None
    

    # Update available map selections if new survey chosen.
    @param.depends("_data_loaded","_listed_survey", watch=True)
    def _update_map_selector(self):
        if self._data_loaded == False or self.tier == "" or self.survey < 0:
            self.param["survey_map"].objects = [""]
            self.survey_map = ""
            return
        logging.info("Updating map selector.")
        maps = schedview.compute.survey.compute_maps(self._listed_survey,
                                                     self._conditions,
                                                     self.nside)
        map_keys = list(maps.keys())
        self.param["survey_map"].objects = map_keys
        if 'reward' in map_keys:                                               # If 'reward' map always exists, then this isn't needed.
            self.survey_map = map_keys[-1]                                     # Reward map usually (always?) listed last.
        else:
            self.survey_map = map_keys[0]
        self._survey_maps = maps
        self.plot_display = 1
    
    
    # Update map selections when nside changed.
    @param.depends("nside", watch=True)
    def _update_nside_of_maps(self):
        if self.tier == "" or self.survey < 0:
            self.param["survey_map"].objects = [""]
            self.survey_map = ""
            return
        logging.info("Updating map resolution (nside).")
        self._survey_maps = schedview.compute.survey.compute_maps(self._listed_survey,
                                                                  self._conditions,
                                                                  self.nside)


    # Update the parameter which determines whether a basis function or a map is plotted.
    @param.depends("survey_map", watch=True)
    def _update_plot_display(self):
        logging.info("Updating parameter for basis/map display.")
        if self.survey_map != "":
            self.plot_display = 1


    # Update basis function table if new survey chosen.
    @param.depends("_listed_survey", watch=True)
    def _update_basis_functions(self):
        if self._listed_survey is None:
            return
        logging.info("Updating basis function dataframe.")
        try:
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            # Check that survey has basis functions.                           # If all surveys have basis functions, this won't be needed.
            if self._rewards.index.isin([(tier_id, survey_id)]).any():
                basis_function_df = schedview.compute.survey.make_survey_reward_df(self._listed_survey,
                                                                                   self._conditions,
                                                                                   self._rewards.loc[[(tier_id, survey_id)], :])
            else:
                self._debugging_message = f"Survey {self.survey} has no basis functions."
                logging.info(f"Survey {self.survey} has no basis functions.")
                self._basis_functions is None
                return
            # Duplicate column and apply URL formatting to one of the columns.
            basis_function_df['basis_func'] = basis_function_df.loc[:, 'basis_function']
            basis_function_df['basis_function'] = basis_function_df.apply(basis_function_url_formatter, axis=1)
            self._basis_functions = basis_function_df
        except:
            self._debugging_message = f"Basis function dataframe unable to be updated: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Basis function dataframe unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self._basis_functions = None


    # Widget for basis function table.
    @param.depends("_basis_functions")
    def basis_function_table(self):
        if self._basis_functions is None:
            return "No basis functions available."
        logging.info("Creating basis function table.")
        tabulator_formatter = {'basis_function': HTMLTemplateFormatter(template='<%= value %>'),
                               'feasible': BooleanFormatter()}
        columnns = ['basis_function',
                    'basis_function_class',
                    'feasible',
                    'max_basis_reward',
                    'basis_area',
                    'basis_weight',
                    'max_accum_reward',
                    'accum_area',
                    'doc_url',
                    'basis_func']
        titles = {
            'basis_function': 'Basis Function',
            'basis_function_class': 'Class',
            'feasible': 'Feasible',
            'max_basis_reward': 'Max Reward',
            'basis_area': 'Area',
            'basis_weight': 'Weight',
            'max_accum_reward': 'Max Accumelated Reward',
            'accum_area': 'Accumelated Area'
        }
        basis_function_table = pn.widgets.Tabulator(self._basis_functions[columnns],
                                                    titles=titles,
                                                    layout="fit_data",
                                                    show_index=False,
                                                    formatters=tabulator_formatter,
                                                    disabled=True,
                                                    frozen_columns=['basis_function'],
                                                    hidden_columns=['basis_func','doc_url'],
                                                    selectable=1,
                                                    pagination='remote',
                                                    page_size=13)
        self._basis_function_df_widget = basis_function_table
        return basis_function_table


    # Update selected basis_function based on row selection of basis_function_table.
    @param.depends("_basis_function_df_widget.selection", watch=True)
    def _update_basis_function_with_row_selection(self):
        if self._basis_function_df_widget.selection == []:
            return
        logging.info("Updating basis function row selection.")
        try:
            self.basis_function = self._basis_function_df_widget.selection[0]  # TODO: TEST BATCH UPDATE HERE
            self.plot_display = 2                                              # Display basis function instead of a map.
            logging.info(f"Basis function selection: {self._basis_functions['basis_func'][self.basis_function]}")
        except:
            self._debugging_message = f"Basis function table selection unable to be updated: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Basis function table selection unable to be updated: \n{traceback.format_exc(limit=-1)}")
            self.basis_function = -1

    
    # Create sky_map of survey for display.
    @param.depends("_conditions","_survey_maps","plot_display","survey_map","basis_function","nside","color_palette")
    def sky_map(self):
        if self._conditions is None:
            return "No scheduler loaded."
        if self._survey_maps is None:
            return "No surveys are loaded."
        
        logging.info("Creating sky map.")
        self._debugging_message = "Creating sky map."
        try:            
            logging.info(f"(plot_display, basis_function, survey_map): ({self.plot_display}, {self.basis_function}, {self.survey_map})")
            self._debugging_message = f"(plot_display, basis_function, survey_map): ({self.plot_display}, {self.basis_function}, {self.survey_map})"
            
            # -----------------------------------------------------------------
            # Load survey map.
            if self.plot_display==1:
                # -------------------------------------------------------------
                # CASE 1: If survey map is all NaNs (i.e. 'reward').
                if np.isnan(self._survey_maps[self.survey_map]).all():
                    
                    logging.info("CASE 1")
                    self._debugging_message = "CASE 1"
                    
                    # Set colormap as Greyscale with -1 as middle color (grey).
                    cmap = bokeh.transform.linear_cmap("value","Greys256",-2,0)
                    
                    # Create array populated with scalar values where sky brightness map is not NaN.
                    scalar_array = self._survey_maps['u_sky'].copy()
                    scalar_array[~np.isnan(self._survey_maps['u_sky'])] = -1
                    
                    # Replace key-pair (map: scalar array) to survey_maps dictionary.
                    self._survey_maps[self.survey_map] = scalar_array
                    
                    # Generate uniform map with tooltip as in non-scalar case.
                    sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                       self._survey_maps,
                                                                       self.survey_map,
                                                                       self.nside,
                                                                       cmap=cmap)
                # -------------------------------------------------------------
                # CASE 2: If survey map is not all NaNs.
                else:
                    logging.info("CASE 2")
                    self._debugging_message = "CASE 2"
                    
                    # Get range of values.
                    min_good_value = np.nanmin(self._survey_maps[self.survey_map])
                    max_good_value = np.nanmax(self._survey_maps[self.survey_map])
                    
                    logging.info(f"(min,max): ({min_good_value},{max_good_value})")
                    self._debugging_message = f"(min,max): ({min_good_value},{max_good_value})"
                    
                    # If all values equal, set colormap to greyscale.
                    if min_good_value == max_good_value:
                        cmap = bokeh.transform.linear_cmap("value","Greys256",min_good_value-1,max_good_value+1)
                    # If all values are not equal, set colormap with selected color_palette.
                    else:
                        cmap = bokeh.transform.linear_cmap("value",self.color_palette,min_good_value,max_good_value)
                    
                    # Generate map.
                    sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                       self._survey_maps,
                                                                       self.survey_map,
                                                                       self.nside,
                                                                       cmap=cmap)
            # -----------------------------------------------------------------
            # Load a basis function map.
            elif self.basis_function!=-1 and self.plot_display==2:
                
                # Get name of basis function.
                bf = self._basis_functions['basis_func'][self.basis_function]
                
                # If area=0, show message in debugging (map will be blank).
                if self._basis_functions.loc[self.basis_function, :]['basis_area'] == 0:
                    logging.info(f"Basis function {bf} has area 0: plot is empty.")
                    self._debugging_message = f"Basis function {bf} has area 0: plot is empty."
                
                # -------------------------------------------------------------
                # CASE 3: If basis function IS in the list of survey maps.
                # (i.e. it is not scalar OR it is scalar, but has already been
                # selected and added to survey maps).
                if any(bf in key for key in self._survey_maps.keys()):
                    
                    logging.info("CASE 3")
                    self._debugging_message = "CASE 3"
                    
                    # Get key name.
                    bf_key = list(key for key in self._survey_maps.keys() if bf in key)[0]
                    
                    # Get range of values.
                    min_good_value = np.nanmin(self._survey_maps[bf_key])
                    max_good_value = np.nanmax(self._survey_maps[bf_key])
                    
                    logging.info(f"(min,max): ({min_good_value},{max_good_value})")
                    self._debugging_message = f"(min,max): ({min_good_value},{max_good_value})"
                    
                    # If all values equal, set colormap to greyscale.
                    if min_good_value == max_good_value:
                        cmap = bokeh.transform.linear_cmap("value","Greys256",min_good_value-1,max_good_value+1)
                    # If all values are not equal, set colormap with selected color_palette.
                    else:
                        cmap = bokeh.transform.linear_cmap("value",self.color_palette,min_good_value,max_good_value)
                        
                    # Generate map.
                    sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                       self._survey_maps,
                                                                       bf_key,
                                                                       self.nside,
                                                                       cmap=cmap)
                # -------------------------------------------------------------
                # CASE 4: If basis function is NOT in list of survey maps
                # (i.e. it is scalar and hasn't yet been selected and added to
                # survey maps).
                else:
                    
                    logging.info("CASE 4")
                    self._debugging_message = "CASE 4"
                    
                    try:
                        # Create array populated with scalar values where sky brightness map is not NaN.
                        scalar_array = self._survey_maps['u_sky'].copy()
                        
                        # Get max_basis_reward.
                        max_basis_reward = self._basis_functions.loc[self.basis_function,:]['max_basis_reward']
                        
                        logging.info(f"max_basis_reward = {max_basis_reward}")
                        self._debugging_message = f"max_basis_reward = {max_basis_reward}"
                        
                        # If max_basis_reward is finite.
                        #if max_basis_reward != -np.nan and max_basis_reward != -np.inf:
                        if max_basis_reward != -np.inf:
                            
                            logging.info("finite")
                            self._debugging_message = "finite"
                            
                            # Create array populated with scalar values where sky brightness map is not NaN.
                            scalar_array[~np.isnan(self._survey_maps['u_sky'])] = self._basis_functions.loc[self.basis_function,:]['max_basis_reward']
                            
                            # Set colormap as Greyscale with value as middle color.
                            cmap = bokeh.transform.linear_cmap("value","Greys256",max_basis_reward-1,max_basis_reward+1)
                            
                        # If max_basis_reward is -inf.
                        else:
                            
                            logging.info("-inf")
                            self._debugging_message = "-inf"
                            
                            # Create array populated with -1 where sky brightness map is not NaN.
                            scalar_array[~np.isnan(self._survey_maps['u_sky'])] = -1
                            
                            # Set colormap as Greyscale with -1 as middle color (grey).
                            cmap = bokeh.transform.linear_cmap("value","Greys256",-2,0) # plot black?
                        
                        # Add new key-pair (basis_function: scalar array) to survey_maps dictionary.
                        self._survey_maps[self._basis_functions['basis_func'][self.basis_function]] = scalar_array
                        
                        # Generate uniform map with tooltip as in non-scalar case.
                        sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                           self._survey_maps,
                                                                           self._basis_functions['basis_func'][self.basis_function],
                                                                           self.nside)
            # -----------------------------------------------------------------
                        
                    except:
                        self._debugging_message = f"Could not load map of scalar basis function: \n{traceback.format_exc(limit=-1)}"
                        logging.info(f"Could not load map of scalar basis function: \n{traceback.format_exc(limit=-1)}")
                        return "Basis function is a scalar."
            sky_map_figure = sky_map.figure
            logging.info("Sky map successfully created.")
            self._debugging_message = "Sky map successfully created."
        except:
            self._debugging_message = f"Could not load map: \n{traceback.format_exc(limit=-1)}"
            logging.info(f"Could not load map: \n{traceback.format_exc(limit=-1)}")
            return "No map loaded."
        return sky_map_figure
    

    # Panel for debugging messages.
    @param.depends("_debugging_message")
    def debugging_messages(self):
        if self._debugging_message is None:
            return
        # Requires astropy only, displays UTC.
        # timestamp_option1 = Time.now().strftime('%Y-%m-%d %H:%M:%S')
        # Requires datetime and pytz, displays Rubin time.
        timestamp_option2 = datetime.now(timezone('America/Santiago')).strftime('%Y-%m-%d %H:%M:%S')
        # Requires astropy and datetime, displays Rubin time.
        # timestamp_option3 = Time(pd.Timestamp(Time.now().datetime, tzinfo=TimezoneInfo(utc_offset=4*u.hour))).strftime('%Y-%m-%d %H:%M:%S')
        self.debug_string = f"\n {timestamp_option2} - {self._debugging_message}" + self.debug_string
        debugging_messages = pn.pane.Str(self.debug_string,
                                         height=70,
                                         styles={'font-size':'9pt',
                                                 'color':'black',
                                                 'overflow': 'scroll'})
        return debugging_messages

# -----------------------------------------------------------------------------

# Generates the key as a Bokeh plot.
def generate_key():
    
    # Number of key items in each column.
    N = 4

    # x,y coordinates for glyphs (lines, circles and text).
    x_title   = np.array([7])    # Title x coord
    y_title   = np.array([5.75]) # Title y coord
    x_circles = np.tile(8,N)     # Circle centre coords
    x_text_1  = np.tile(2.5,N)   # Text in colunn 1
    x_text_2  = np.tile(8.75,N)  # Text in column 2
    x0_lines  = np.tile(0.75,N)  # Start lines
    x1_lines  = np.tile(2,N)     # End lines
    y = np.arange(N,0,-1)        # y coords for all items except title

    # Colours and sizes of images.
    line_colours   = np.array(['black','red','#1f8f20','#110cff'])
    circle_colours = np.array(['#ffa500','grey','red','#1f8f20'])
    circle_sizes   = np.tile(10,N)
    
    # Text for title and key items.
    title_text = np.array(['Key'])
    text_1     = np.array(['Horizon','ZD=70 degrees','Ecliptic','Galactic plane'])                 # Column 1
    text_2     = np.array(['Sun position','Moon position','Survey field(s)','Telescope pointing']) # Column 2
    
    # Assign above data to relevant data source (to be used in glyph creation below).
    title_source  = bokeh.models.ColumnDataSource(dict(x=x_title, y=y_title, text=title_text))
    text1_source  = bokeh.models.ColumnDataSource(dict(x=x_text_1, y=y, text=text_1))
    text2_source  = bokeh.models.ColumnDataSource(dict(x=x_text_2, y=y, text=text_2))
    circle_source = bokeh.models.ColumnDataSource(dict(x=x_circles, y=y, sizes=circle_sizes, colours=circle_colours))
    line_source   = bokeh.models.ColumnDataSource(dict(x0=x0_lines, y0=y, x1=x1_lines,y1=y, colours=line_colours))

    # Create glyphs.
    border_glyph = bokeh.models.Rect(x=7, y=3.25, width=14, height=6.5, line_color="#048b8c", fill_color=None, line_width=3)
    header_glyph = bokeh.models.Rect(x=7, y=5.75, width=14, height=1.5, line_color=None,      fill_color="#048b8c")
    title_glyph  = bokeh.models.Text(x='x', y='y', text='text', text_font_size='15px', text_color='white', text_baseline='middle', text_font = {'value': 'verdana'}, text_align='center')#, text_font_style='bold'
    text1_glyph  = bokeh.models.Text(x="x", y="y", text="text", text_font_size='10px', text_color="black", text_baseline='middle', text_font = {'value': 'verdana'})
    text2_glyph  = bokeh.models.Text(x="x", y="y", text="text", text_font_size='10px', text_color="black", text_baseline='middle', text_font = {'value': 'verdana'})
    circle_glyph = bokeh.models.Circle(x="x", y="y", size="sizes", line_color="colours", fill_color="colours")
    line_glyph   = bokeh.models.Segment(x0="x0", y0="y0", x1="x1", y1="y1", line_color="colours", line_width=2, line_cap='round')
    
    # Create plot.
    plot = bokeh.models.Plot(title=None, width=300, height=150, min_border=0, toolbar_location=None)

    # Add glyphs to plot.
    plot.add_glyph(border_glyph)
    plot.add_glyph(header_glyph)
    plot.add_glyph(title_source,  title_glyph)
    plot.add_glyph(text1_source,  text1_glyph)
    plot.add_glyph(text2_source,  text2_glyph)
    plot.add_glyph(circle_source, circle_glyph)
    plot.add_glyph(line_source,   line_glyph)
    
    return plot

# -----------------------------------------------------------------------------

def scheduler_app(date=None, scheduler_pickle=None):
    
    scheduler = Scheduler()
    
    if date is not None:
        scheduler.date = date
    
    if scheduler_pickle is not None:
        scheduler.scheduler_fname = scheduler_pickle
    
    sched_app = pn.GridSpec(sizing_mode='stretch_both', max_height=1000).servable()
    
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
                                        parameters=["scheduler_fname","date","tier"],
                                        widgets={'scheduler_fname':{'widget_type':pn.widgets.TextInput,
                                                                    'placeholder':'filepath or URL of pickle'},
                                                 'date':pn.widgets.DatetimePicker},
                                        name="Select pickle file, date and tier.")
    # Survey rewards table and header.
    sched_app[8:33, 21:67]   = pn.Row(pn.Spacer(width=10),
                                      pn.Column(pn.Spacer(height=10),
                                                pn.Row(scheduler.survey_rewards_title,
                                                       styles={'background':'#048b8c'}),
                                                pn.param.ParamMethod(scheduler.survey_rewards_table, loading_indicator=True)),
                                      pn.Spacer(width=10),
                                      sizing_mode='stretch_height')
    # Basis function table and header.
    sched_app[33:87, 0:67]   = pn.Row(pn.Spacer(width=10),
                                      pn.Column(pn.Spacer(height=10),
                                                pn.Row(scheduler.basis_function_table_title,
                                                       styles={'background':'#048b8c'}),
                                                pn.param.ParamMethod(scheduler.basis_function_table, loading_indicator=True)),
                                      pn.Spacer(width=10))
    # Map display and header.
    sched_app[8:59, 67:100]  = pn.Column(pn.Spacer(height=10),
                                         pn.Row(scheduler.map_title,styles={'background':'#048b8c'}),
                                         pn.param.ParamMethod(scheduler.sky_map, loading_indicator=True))
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