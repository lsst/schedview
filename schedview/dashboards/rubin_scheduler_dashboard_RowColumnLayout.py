import param
import pandas as pd
import panel as pn
import numpy as np   # used once; not really neccessary
import bokeh
import logging
import os

from astropy.time import Time
from zoneinfo import ZoneInfo
from bokeh.models.widgets.tables import HTMLTemplateFormatter

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
    
    1. Display scalar maps of basis functions with scalar value.
    2. Link color palette drop down selection to map color palette.
    3. Check if able to load pickle from a URL.
    4. Make a key from bokeh.
    5. Implement Eman's changes:
        - fonts
        - survey links
        - debugger text wrapping
        - logo alignment in row/column layout
        - terminal pane (what was wrong with this?)
        - URL image path (instead of local path)


Current issues/quirks:
---------------------

    Map display:

        a) Sometimes a map gets "stuck" loading:
            (Occurs when the current selection of survey_map != 'reward' and
             a new survey is chosen, and when a new tier + survey is chosen.)
        b) Survey maps with non-numeric rewards do not display a map, although
           'reward' is shown as an option in survey_map selection.
           RuntimeWarning: All-NaN slice encountered; np.nanmax(hpix_data[map_key])
        c) When changing nside, and occassionally when selecting a survey or
           basis function, a deserialisation error is thrown with no noticable
           consequences:
               ERROR:bokeh.server.protocol_handler:error handling message
               error: DeserializationError("can't resolve reference 'p6667'")
    
    Survey_map selection:
        
        - When a (non-scalar) basis function is selected from the table, perhaps
          the survey_map drop-down selector should change to reflect this?
        - If it does change, what happens then when a scalar basis function is
          selected? What should be shown at the survey_map drop-down?

    [DONE] Logo:
        
        - GridSpec layout:   logo aligned correctly.
        - Row/column layout: there is an unexplainable gap on the right side
                             of the Rubin logo.
    
    [DONE] Debugger/error log options:
        
        a) Debugger: unsightly and the messages (all levels) are useless.
        b) Terminal: slightly less unsightly and useful errors
        c) Custom debugger: pretty, customisable, but text won't stay in box.
    
    Layout:
        
        - Row/column: all rows/columns are equally divided.
        - GridSpec:   custom spacing but tables/map overrun their spaces.
    
    Updates:
        
        a) When an unloadable pickle is loaded after a loadable pickle, user
           gets a message that pickle can't be loaded, but all data of loadable
           pickle stays accessible.
               - Is this behaviour okay?
        b) When an invalid date is chosen after a valid date, survey title,
           survey table, and basis function table disappear, but basis function
           table title, map title and map stay on screen.
               - Should all data, no data or some data remain on screen?


Pending questions
-----------------
    
    - Are users choosing a date or a datetime?
    - Do we have a pickle at a URL we can test with?

"""

DEFAULT_TIMEZONE        = "Chile/Continental"
DEFAULT_CURRENT_TIME    = Time.now()
DEFAULT_SCHEDULER_FNAME = "scheduler.pickle.xz"

color_palettes = [s for s in bokeh.palettes.__palettes__ if "256" in s]

LOGO = "/assets/lsst_white_logo.png"
key_image = "/assets/key_image.png"

pn.extension("tabulator",
             css_files   = [pn.io.resources.CSS_URLS["font-awesome"]],
             sizing_mode = "stretch_width",)

#pn.widgets.Tabulator.theme = 'site'

pn.config.console_output = "disable"                                           # To avoid clutter.

logging.basicConfig(format = "%(asctime)s %(message)s",
                    level  = logging.INFO)

debug_info = pn.widgets.Debugger(name        = "Debugger information.",
                                 level       = logging.DEBUG,
                                 sizing_mode = "stretch_both")

terminal = pn.widgets.Terminal(height=100, sizing_mode='stretch_width')


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
    date            = param.Date(DEFAULT_CURRENT_TIME.datetime.date())
    tier            = param.ObjectSelector(default="", objects=[""])
    survey          = param.Integer(default=-1)
    basis_function  = param.Integer(default=-1)
    survey_map      = param.ObjectSelector(default="", objects=[""])
    plot_display    = param.Integer(default=1)
    nside           = param.ObjectSelector(default=16,
                                           objects=[2**n for n in np.arange(1, 6)],
                                           label="Map resolution (nside)")
    color_palette   = param.ObjectSelector(default="Magma256",
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
    
    
    # Dashboard headings ------------------------------------------------------# Should these functions be below others?
    
    # Panel for dashboard title.
    @param.depends("tier", "survey", "plot_display", "survey_map", "basis_function")
    def dashboard_title(self):
        titleT  = ''; titleS  = ''; titleBF = ''; titleM = ''
        if self._scheduler is not None:
            if self.tier != '':
                titleT = '\nTier {}'.format(self.tier[-1])
                if self.survey >= 0:
                    titleS = ' | Survey {}'.format(self.survey)
                    if self.plot_display == 1:
                        titleM = ' | Map {}'.format(self.survey_map)
                    elif self.plot_display == 2 and self.basis_function >= 0:
                        titleBF = ' | Basis function {}'.format(self.basis_function)
        title_string = 'Scheduler Dashboard' + titleT + titleS + titleBF + titleM
        dashboard_title = pn.pane.Str(title_string,styles={'font-size':'16pt',
                                                           'color':'white',
                                                           'font-weight':'bold'},
                                                    stylesheets=[title_stylesheet])
        return dashboard_title


    # Panel for survey rewards table title.
    @param.depends("tier")
    def survey_rewards_title(self):
        title_string = ''
        if self._scheduler is not None and self.tier != '':
            title_string = 'Tier {} survey rewards'.format(self.tier[-1])
        survey_rewards_title = pn.pane.Str(title_string, styles={'font-size':'14pt',
                                                                 'color':'white'},
                                                        stylesheets=[title_stylesheet])
        return survey_rewards_title


    # Panel for basis function table title.
    @param.depends("survey")
    def basis_function_table_title(self):        
        if self._scheduler is not None and self.survey >= 0:
            title_string = 'Basis functions for survey {}'.format(self._tier_survey_rewards.reset_index()['survey_name'][self.survey])
        else:
            title_string = ''
        basis_function_table_title = pn.pane.Str(title_string, 
                                                styles={'font-size':'14pt',
                                                        'color':'white'},
                                                stylesheets=[another_title_stylesheet], 
                                                css_classes=['title'])
        return basis_function_table_title


    # Panel for map title.
    @param.depends("survey", "plot_display", "survey_map", "basis_function")
    def map_title(self):
        if self._scheduler is not None and self.survey >= 0:
            titleA = 'Survey {}\n'.format(self._tier_survey_rewards.reset_index()['survey_name'][self.survey])
            if self.plot_display == 1:
                titleB = 'Map {}'.format(self.survey_map)
            elif self.plot_display == 2 and self.basis_function >= 0:
                titleB = 'Basis function {}: {}'.format(self.basis_function,
                                                        self._basis_functions['basis_function'][self.basis_function])
            else:
                titleA = ''; titleB = ''
            title_string = titleA + titleB
        else:
            title_string = ''
        map_title = pn.pane.Str(title_string, styles={'font-size':'14pt',
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
            self._scheduler = scheduler
            self._conditions = conditions
        except Exception as e:
            logging.error(f"Could not load scheduler from {self.scheduler_fname} {e}")
            self._debugging_message = f"Could not load scheduler from {self.scheduler_fname}: {e}"
            terminal.write(f"\n {Time.now().iso} - Could not load scheduler from {self.scheduler_fname}: {e}")
    
    
    # Update datetime if new datetime chosen.
    @param.depends("date", watch=True)
    def _update_date_time(self):
        logging.info("Updating date.")
        self._date_time = Time(pd.Timestamp(self.date, tzinfo=ZoneInfo("Chile/Continental"))).mjd
        logging.info("Date updated to {}".format(self._date_time))
    
    
    # Update survey reward table if given new pickle file or new date.
    @param.depends("_scheduler", "_conditions", "_date_time", watch=True)
    def _update_survey_rewards(self):
        if self._scheduler is None:
            logging.info("No pickle loaded.")
            return
        logging.info("Updating survey rewards.")
        try:
            self._conditions.mjd = self._date_time
            self._scheduler.update_conditions(self._conditions)
            self._rewards  = self._scheduler.make_reward_df(self._conditions)
            survey_rewards = schedview.compute.scheduler.make_scheduler_summary_df(self._scheduler,
                                                                                   self._conditions,
                                                                                   self._rewards)
            survey_rewards['survey_name'] = survey_rewards.apply(survey_url_formatter, axis=1)
            self._survey_rewards = survey_rewards
        except Exception as e:
            logging.error(e)
            logging.info("Survey rewards table unable to be updated. Perhaps date not in range of pickle data?")
            self._debugging_message = "Survey rewards table unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Survey rewards table unable to be updated: {e}")
            self._survey_rewards = None


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
    @param.depends("_survey_rewards", "tier", watch=True)
    def _update_survey_reward_table(self):
        if self._survey_rewards is None:
            self._tier_survey_rewards = None
            return
        logging.info("Updating survey rewards for chosen tier.")
        try:
            self._tier_survey_rewards = self._survey_rewards[self._survey_rewards['tier']==self.tier]
        except Exception as e:
            logging.error(e)
            self._debugging_message = "Survey rewards unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Survey rewards unable to be updated: {e}")
            self._tier_survey_rewards = None


    # Widget for survey reward table.
    @param.depends("_tier_survey_rewards")
    def survey_rewards_table(self):
        if self._tier_survey_rewards is None:
            return "No surveys available."
        
        tabulator_formatter = {
            'survey_name': HTMLTemplateFormatter(template='<%= value %>')
        }
        survey_rewards_table = pn.widgets.Tabulator(self._tier_survey_rewards[['tier','survey_name','reward','survey_url']],
                                                    widths={'survey_name':'60%','reward':'40%'},
                                                    show_index=False,
                                                    formatters=tabulator_formatter,
                                                    disabled=True,
                                                    selectable=1,
                                                    hidden_columns=['tier','survey_url'],
                                                    #height=200,
                                                    sizing_mode='stretch_width',
                                                    #sizing_mode='stretch_both',
                                                    )
        logging.info("Finished updating survey rewards table.")
        self._survey_df_widget = survey_rewards_table
        return survey_rewards_table


    # Update selected survey based on row selection of survey_rewards_table.
    @param.depends("_survey_df_widget.selection", watch=True)
    def update_survey_with_row_selection(self):
        logging.info("Updating survey row selection.")
        if self._survey_df_widget.selection == []:
            self.survey = -1
            return
        try:
            self.survey = self._survey_df_widget.selection[0]
        except Exception as e:
            logging.error(e)
            self._debugging_message = "Survey selection unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Survey selection unable to be updated: {e}")
            self.survey = -1                                                   # When no survey selected, survey = -1
    
    
    # Update listed_survey if tier or survey selections change.
    @param.depends("survey", watch=True)
    def _update_listed_survey(self):
        logging.info("Updating listed survey.")
        try:
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            self._listed_survey = self._scheduler.survey_lists[tier_id][survey_id]
        except Exception as e:
            logging.error(e)
            self._debugging_message = "Listed survey unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Listed survey unable to be updated: {e}")
            self._listed_survey = None
    

    # Update available map selections if new survey chosen.                    # Add try-catch here?
    @param.depends("_listed_survey", watch=True)
    def _update_map_selector(self):
        if self.tier == "" or self.survey < 0:
            self.param["survey_map"].objects = [""]
            self.survey_map = ""
            return
        logging.info("Updating map selector.")
        self._survey_maps = schedview.compute.survey.compute_maps(self._listed_survey,
                                                                  self._conditions,
                                                                  self.nside)
        maps = list(self._survey_maps.keys())
        self.param["survey_map"].objects = maps
        if 'reward' in maps:                                                   # If 'reward' map always exists, then this isn't needed.
            self.survey_map = maps[-1]                                         # Reward map usually (always?) listed last.
        else:
            self.survey_map = maps[0]
        self.plot_display = 1
        
    
    # Update map selections when nside changed.                                # Add try-catch here?
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
        #self.plot_display = 1         # Display map instead of basis function.
        if self.survey_map != "":
            self.plot_display = 1


    # Update basis function table if new survey chosen.
    @param.depends("_listed_survey", "survey_rewards_table", watch=True)
    def _update_basis_functions(self):
        if self._listed_survey is None:
            return
        logging.info("Updating basis function table.")
        try:
            tier_id = int(self.tier[-1])
            survey_id = self.survey
            basis_function_df = schedview.compute.survey.make_survey_reward_df(self._listed_survey,
                                                                               self._conditions,
                                                                               self._rewards.loc[[(tier_id, survey_id)], :])
            self._basis_functions = basis_function_df
        except Exception as e:
            logging.error(e)
            self._debugging_message = "Basis function dataframe unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Basis function dataframe unable to be updated: {e}")
            self._basis_functions = None


    # Widget for basis function table.
    @param.depends("_basis_functions")
    def basis_function_table(self):
        if self._basis_functions is None:
            return "No basis functions available."
        logging.info("Creating basis function table.")
        tabulator_formatter = {
            'basis_function': {'type': 'link',
                                'labelField':'basis_function',
                                'urlField':'doc_url',
                                'target':'_blank'}}
        columnns = ['basis_function',
                    'basis_function_class',
                    'feasible',
                    'max_basis_reward',
                    'basis_area',
                    'basis_weight',
                    'max_accum_reward',
                    'accum_area',
                    'doc_url']
        basis_function_table = pn.widgets.Tabulator(self._basis_functions[columnns],
                                                    layout="fit_data",
                                                    show_index=False,
                                                    formatters=tabulator_formatter,
                                                    disabled=True,
                                                    frozen_columns=['basis_function'],
                                                    hidden_columns=['doc_url'],
                                                    selectable=1,
                                                    #height=500,
                                                    #sizing_mode='stretch_both',
                                                    )
        self._basis_function_df_widget = basis_function_table
        return basis_function_table


    # Update selected basis_function based on row selection of basis_function_table.
    @param.depends("_basis_function_df_widget.selection", watch=True)
    def update_basis_function_with_row_selection(self):
        if self._basis_function_df_widget.selection == []:
            return
        logging.info("Updating basis function row selection.")
        try:
            self.plot_display = 2                                              # Display basis function instead of a map.
            self.basis_function = self._basis_function_df_widget.selection[0]
            logging.info(f"Basis function selection: {self._basis_functions['basis_function'][self.basis_function]}")
        except Exception as e:
            logging.error(e)
            self._debugging_message = "Basis function dataframe selection unable to be updated: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Basis function dataframe selection unable to be updated: {e}")
            self.basis_function = -1                                           # When no basis function selected, basis_function = -1.


    # Create sky_map of survey for display.
    @param.depends("_conditions","_survey_maps","plot_display","survey_map","basis_function","nside")
    def sky_map(self):
        if self._conditions is None:
            return "No scheduler loaded."
        if self._survey_maps is None:
            return "No surveys are loaded."
        try:
            # Load survey map.
            if self.plot_display==1: #self.basis_function == -1:
                sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                   self._survey_maps,
                                                                   self.survey_map,
                                                                   self.nside)
            # Load a basis function map.
            elif self.basis_function!=-1 and self.plot_display==2:
                bf = self._basis_functions['basis_function'][self.basis_function]
                # Is the basis function in the list of survey maps?
                if any(bf in key for key in self._survey_maps.keys()):
                    # Get key name
                    bf_key = list(key for key in self._survey_maps.keys() if bf in key)[0]
                    # Generate map
                    sky_map = schedview.plot.survey.map_survey_healpix(self._conditions.mjd,
                                                                       self._survey_maps,
                                                                       bf_key,
                                                                       self.nside)
                # If the basis function is not in the list of survey maps, it is scalar.
                else:
                    logging.info("Could not load map of scalar basis function.")
                    self._debugging_message = "Could not load map of scalar basis function."
                    terminal.write(f"\n {Time.now().iso} - Could not load map of scalar basis function.")
                    return "Basis function is a scalar; scalar maps not yet implemented."
                
            sky_map_figure = sky_map.figure
            logging.info("Map successfully created.")
        except Exception as e:
            logging.info("Could not load map:")
            logging.error(e)
            self._debugging_message = "Could not load map: " + str(e)
            terminal.write(f"\n {Time.now().iso} - Could not load map: {e}")
            return "No map loaded."
        return sky_map_figure
    

    # Panel for debugging messages
    @param.depends("_debugging_message")
    def debugging_messages(self):
        if self._debugging_message is None:
            return
        self.debug_string += f"\n {Time.now().iso} - {self._debugging_message}"
        debugging_messages = pn.pane.Str(self.debug_string,
                                         height=80,
                                         #width=800,
                                         #sizing_mode='stretch_width',
                                         styles={'font-size':'9pt',
                                                 'color':'black',
                                                 'overflow': 'scroll'})
        return debugging_messages
    

def scheduler_app(date=None, scheduler_pickle=None):
    
    scheduler = Scheduler()
    
    if date is not None:
        scheduler.date = date
    
    if scheduler_pickle is not None:
        scheduler.scheduler_fname = scheduler_pickle
    
    # Dashboard layout.
    sched_app = pn.Column(
        # Title pane across top of dashboard.
        pn.Row(scheduler.dashboard_title,
                pn.layout.HSpacer(),
                pn.pane.PNG(LOGO, height=80, align='center', margin=(5,5,5,5)),
                sizing_mode='stretch_width',
                styles={'background':'#048b8c'}),
        pn.Spacer(height=10),
        # Rest of dashboard.
        pn.Row(
            # LHS column (inputs, tables).
            pn.Spacer(width=10),
            pn.Column(
                # Top-left (inputs, survey table).
                pn.Row(
                    pn.Column(
                        pn.Param(scheduler,
                                  parameters=["scheduler_fname","date","tier"],
                                  widgets={'scheduler_fname':{'widget_type':pn.widgets.TextInput,
                                                              'placeholder':'filepath or URL of pickle'},
                                           'date':pn.widgets.DatetimePicker},
                                  name="Select pickle file, date and tier."),
                        ),
                    pn.Column(
                        pn.Row(scheduler.survey_rewards_title,styles={'background':'#048b8c'}),
                        pn.param.ParamMethod(scheduler.survey_rewards_table, loading_indicator=True)
                        )
                    ),
                # Bottom-left (basis function table).
                pn.Spacer(height=10),
                pn.Row(scheduler.basis_function_table_title, styles={'background':'#048b8c'}),
                pn.param.ParamMethod(scheduler.basis_function_table, loading_indicator=True)
                ),
            pn.Spacer(width=10),
            # RHS column (map, key).
            pn.Column(
                # Top-right (map).
                pn.Row(scheduler.map_title,styles={'background':'#048b8c'}),
                pn.param.ParamMethod(scheduler.sky_map, loading_indicator=True),
                # Bottom-right (key, map parameters).
                pn.Row(
                    pn.pane.PNG(key_image, height=200),
                    pn.Column(
                        pn.Param(scheduler,
                                  parameters=["survey_map","nside","color_palette"],
                                  name="Map, resolution, & color scheme.")#,
                                  #show_name=False)
                        )
                    )
                ),
            pn.Spacer(width=10)
            ),
        
        # Debugger. - (3 options)
        
        # OPTION 1
        #debug_info
        
        # OPTION 2
        # pn.Row(
        #     pn.Spacer(width=10),
        #     pn.Column(
        #         pn.pane.Str(' Debugging', align='center', styles={'font-size':'10pt','color':'black'}),
        #         terminal,
        #         styles={'background':'#EDEDED'}
        #         ),
        #     pn.Spacer(width=10)
        #     )
        
        # OPTION 3
        pn.Column(pn.pane.Str(' Debugging', styles={'font-size':'10pt','font-weight':'bold','color':'black'}),
                  scheduler.debugging_messages,
                  #pn.layout.HSpacer(),
                #   sizing_mode='stretch_width',
                #   width_policy='max',
                  height=100,
                  styles={'background':'#EDEDED'}
                  )
        
        ).servable()

    return sched_app

    
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