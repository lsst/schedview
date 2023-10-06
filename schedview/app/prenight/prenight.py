import argparse
import importlib.resources
import json
import logging
import os
import sys
from glob import glob

import astropy.utils.iers
import bokeh
import hvplot.pandas  # noqa: F401
import numpy as np
import pandas as pd
import panel as pn
import param
import rubin_sim.scheduler.example
from astropy.time import Time
from rubin_sim.scheduler.model_observatory import ModelObservatory
from rubin_sim.utils import survey_start_mjd

import schedview.collect.footprint
import schedview.collect.opsim
import schedview.compute.astro
import schedview.compute.scheduler
import schedview.param
import schedview.plot.nightbf
import schedview.plot.nightly
import schedview.plot.rewards
import schedview.plot.visitmap
import schedview.plot.visits

AVAILABLE_TIMEZONES = [
    "Chile/Continental",
    "US/Pacific",
    "US/Arizona",
    "US/Mountain",
    "US/Central",
    "US/Eastern",
]
DEFAULT_TIMEZONE = AVAILABLE_TIMEZONES[0]
DEFAULT_CURRENT_TIME = Time(max(Time.now().mjd, survey_start_mjd()), format="mjd")
USE_EXAMPLE_SCHEDULER = False
DEFAULT_MODEL_OBSERVATORY = ModelObservatory(init_load_length=1)
DEFAULT_MODEL_OBSERVATORY.sky_model.load_length = 1

PACKAGE_DATA_DIR = importlib.resources.files("schedview.data").as_posix()
USDF_DATA_DIR = "/sdf/group/rubin/web_data/sim-data/schedview"

astropy.utils.iers.conf.iers_degraded_accuracy = "warn"

pn.extension(
    "tabulator",
    css_files=[pn.io.resources.CSS_URLS["font-awesome"]],
    sizing_mode="stretch_width",
)
pn.config.console_output = "accumulate"


class Prenight(param.Parameterized):
    """The pre-night briefing application."""

    custom_hvplot_tab_settings_file = param.FileSelector(
        default="",
        doc="The file containing the settings for the custom hvplot tabs.",
        label="Custom hvplot tab settings",
    )

    _custom_hvplot_tab_settings = param.Parameter(
        default=[],
        doc="The settings for the custom hvplot tabs.",
    )

    shown_tabs = param.ListSelector(
        default=[
            "Azimuth and altitude",
            "Airmass vs. time",
            "Sky maps",
            "Table of visits",
            "Reward plots",
        ],
        objects=[
            "Azimuth and altitude",
            "Airmass vs. time",
            "Sky maps",
            "Table of visits",
            "Reward plots",
            "Visit explorer",
        ],
        doc="The names of the tabs to show.",
    )

    opsim_output_fname = param.String(
        doc="The file name or URL of the OpSim output database.",
        label="OpSim output database path or URL",
    )

    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
Such a pickle file can either be of an instance of a subclass of
rubin_sim.scheduler.schedulers.CoreScheduler, or a tuple of the form
(scheduler, conditions), where scheduler is an instance of a subclass of
rubin_sim.scheduler.schedulers.CoreScheduler, and conditions is an
instance of rubin_sim.scheduler.conditions.Conditions."""
    scheduler_fname = param.String(
        doc=scheduler_fname_doc,
        label="URL or file name of scheduler pickle file",
    )

    rewards_fname = param.String(
        doc="URL or file name of the rewards HDF5 file.",
        label="URL or file name of rewards HDF5 file",
    )

    # Express the night as an instance of datetime.date, so that it can be
    # used with the panel.widgets.DatePicker widget.
    # It represents the local calendar date of sundown for the night to view.
    night = param.Date(
        default=DEFAULT_CURRENT_TIME.datetime.date(),
        doc="The local calendar date of sundown for the night to view.",
        label="Night to view (local time at sunset)",
    )

    timezone = param.ObjectSelector(
        objects=AVAILABLE_TIMEZONES,
        default=DEFAULT_TIMEZONE,
        doc='The timezone in which "local time" is to be shown.',
        label="Timezone",
    )

    tier = param.ObjectSelector(
        default="",
        objects=[""],
        doc="The label for the first index into the CoreScheduler.survey_lists.",
        label="Tier",
    )
    surveys = param.ListSelector(
        objects=[],
        default=[],
        doc="The labels for the second index into the CoreScheduler.survey_lists.",
        label="Surveys",
    )
    basis_function = param.ObjectSelector(
        default="",
        objects=[""],
        doc="The label for the basis function to be shown.",
        label="Basis function",
    )

    _observatory = DEFAULT_MODEL_OBSERVATORY
    _site = _observatory.location
    # Must declare all of these as Parameters, even though they should not
    # be set by the user, because they are used in the @depends methods,
    # and otherwise Parametrized will assume that they depend on
    # everything.
    _visits = schedview.param.DataFrame(
        None,
        doc="The visits for the night.",
        columns={
            "fieldRA": float,
            "fieldDec": float,
            "observationStartMJD": float,
            "filter": str,
            "rotSkyPos": float,
            "rotSkyPos_desired": float,
        },
    )

    # If the bokeh.models.ColumnDataSource is created once and used in
    # multiple plots, then the plots can be more easily linked, and memory
    # and communication overhead is reduced.
    _visits_cds = param.Parameter()

    # An instance of rubin_sim.scheduler.schedulers.CoreScheduler
    _scheduler = param.Parameter()

    _almanac_events = schedview.param.DataFrame(
        None,
        doc="Events from the rubin_sim alamanc",
        columns={"MJD": float, "LST": float, "UTC": pd.Timestamp},
    )

    _reward_df = schedview.param.DataFrame(
        None,
        columns={
            "basis_function": str,
            "feasible": np.bool_,
            "max_basis_reward": float,
            "basis_area": float,
            "basis_weight": float,
            "tier_label": str,
            "survey_label": str,
            "survey_class": str,
            "survey_reward": float,
            "basis_function_class": object,
            "queue_start_mjd": float,
            "queue_fill_mjd_ns": np.int64,
        },
    )
    _obs_rewards = schedview.param.Series()

    def __init__(self, **params):
        super().__init__(**params)
        self.config_logger()

        # Make sure the display elements that depend on the
        # night are initialized, because param won't automatically
        # update them if the night is not changed.
        # That is, if we do not do this, things will fail if the sure
        # wants to look at the default night.
        self.param.trigger("night")

    def config_logger(self, logger_name="prenight"):
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

    @param.depends("custom_hvplot_tab_settings_file", watch=True)
    def _update_custom_hvplot_tab_settings(self):
        if len(self.custom_hvplot_tab_settings_file) < 1:
            return None

        with open(self.custom_hvplot_tab_settings_file, "r") as fp:
            self._custom_hvplot_tab_settings = json.load(fp)

    @param.depends("_custom_hvplot_tab_settings", watch=True)
    def _update_shown_tabs_options(self):
        current_selections = [str(s) for s in self.shown_tabs]

        new_objects = [
            "Azimuth and altitude",
            "Airmass vs. time",
            "Sky maps",
            "Table of visits",
            "Reward plots",
            "Visit explorer",
        ] + [p["name"] for p in self._custom_hvplot_tab_settings]

        new_shown_tabs = [s for s in current_selections if s in new_objects]

        for custom_tab in self._custom_hvplot_tab_settings:
            if custom_tab["name"] not in new_shown_tabs:
                new_shown_tabs.append(custom_tab["name"])

        self.param["shown_tabs"].objects = new_objects
        self.shown_tabs = new_shown_tabs

    @param.depends("night", "timezone", watch=True)
    def _update_almanac_events(self):
        self.logger.info("Updating almanac events.")
        night_events = schedview.compute.astro.night_events(self.night, self._site, self.timezone)

        # Bokeh automatically converts all datetimes to UTC
        # when displaying, which we do not want. So, turn the localized
        # datetimes to naive datetimes so bokeh leaves them alone.
        night_events[self.timezone] = night_events[self.timezone].dt.tz_localize(None)

        self._almanac_events = night_events

    @param.depends("_almanac_events")
    def almanac_events_table(self):
        if self._almanac_events is None:
            return "No almanac events computed."

        self.logger.info("Starting to update almanac table.")
        almanac_table = pn.widgets.Tabulator(self._almanac_events)
        self.logger.info("Finished updating almanac table.")
        return almanac_table

    @param.depends("opsim_output_fname", "_almanac_events", watch=True)
    def _update_visits(self):
        if (
            self.opsim_output_fname is None
            or len(self.opsim_output_fname) == 0
            or self._almanac_events is None
        ):
            self._visits = None
            return

        self.logger.info("Starting to update visits.")
        try:
            if not os.path.exists(self.opsim_output_fname):
                raise FileNotFoundError(f"File not found: {self.opsim_output_fname}")

            visits = schedview.collect.opsim.read_opsim(
                self.opsim_output_fname,
                Time(self._almanac_events.loc["sunset", "UTC"]),
                Time(self._almanac_events.loc["sunrise", "UTC"]),
            )
            self._visits = visits
            self.logger.info("Finish updating visits DataFrame.")
            self.logger.info("Starting to update visits ColumnDataSource.")
            self._visits_cds = bokeh.models.ColumnDataSource(visits)
            self.logger.info("Finished updating visits ColumnDataSource.")

        except Exception as e:
            self.logger.info("Error updating visits.")
            self.logger.error(e)
            self._visits = None
            self._visits_cds = None

    @param.depends("_visits")
    def visit_table(self):
        """Create a tabuler display widget with visits.

        Returns
        -------
        visit_table : `pn.widgets.Tabulator`
            The table of visits.
        """
        if self._visits is None:
            return "No visits loaded."

        self.logger.info("Updating visit tabulator widget")
        columns = [
            "start_date",
            "fieldRA",
            "fieldDec",
            "altitude",
            "azimuth",
            "filter",
            "airmass",
            "slewTime",
            "moonDistance",
            "block_id",
            "note",
        ]

        visit_table = pn.widgets.Tabulator(self._visits[columns], pagination="remote", header_filters=True)

        if len(self._visits) < 1:
            visit_table = "No visits on this night"

        self.logger.info("Finished updating visit tabulator widget")
        return visit_table

    @param.depends("_visits")
    def visit_explorer(self):
        """Create holoviz explorer on the visits.

        Returns
        -------
        visit_explorer : `hvplot.ui.hvDataFrameExplorer`
            The holoviz plot of visits.
        """
        if self._visits is None:
            return "No visits loaded."

        self.logger.info("Starting to update visit explorer")

        (
            visit_explorer,
            visit_explorer_data,
        ) = schedview.plot.visits.create_visit_explorer(
            visits=self._visits,
            night_date=self.night,
        )

        if len(visit_explorer_data["visits"]) < 1:
            visit_explorer = "No visits on this night."

        self.logger.info("Finished updating visit explorer")

        return visit_explorer

    def hvplot(self, custom_plot_index):
        if len(self.custom_hvplot_tab_settings_file) <= custom_plot_index:
            return None

        if self._visits is None:
            return "No visits loaded."

        if len(self._visits) < 1:
            return "Visits loaded, but no visits on this night."

        custom_plot_name = self._custom_hvplot_tab_settings[custom_plot_index]["name"]
        self.logger.info(f"Starting to create custom hvplot {custom_plot_index} ({custom_plot_name})")
        try:
            plot = self._visits.hvplot(**self._custom_hvplot_tab_settings[custom_plot_index]["settings"])
            self.logger.info(f"Finished creating custom hvplot {custom_plot_index}")
        except Exception as e:
            self.logger.error(f"Could not create custom hvplot: {e}")
            return f"Error creating custom hvplot: {e}"

        return plot

    @param.depends("_visits")
    def custom_hvplot0(self):
        return self.hvplot(0)

    @param.depends("_visits")
    def custom_hvplot1(self):
        return self.hvplot(1)

    @param.depends("_visits")
    def custom_hvplot2(self):
        return self.hvplot(2)

    @param.depends("_visits")
    def custom_hvplot3(self):
        return self.hvplot(3)

    @param.depends("_visits")
    def custom_hvplot4(self):
        return self.hvplot(4)

    @param.depends("scheduler_fname", watch=True)
    def _update_scheduler(self):
        self.logger.info("Starting to update the scheduler.")
        try:
            (
                scheduler,
                conditions,
            ) = schedview.collect.scheduler_pickle.read_scheduler(self.scheduler_fname)

            self._scheduler = scheduler
            self.logger.info("Finished updating the scheduler.")
        except Exception as e:
            self.logger.error(f"Could not load scheduler from {self.scheduler_fname} {e}")
            if USE_EXAMPLE_SCHEDULER:
                self.logger.info("Starting to load example scheduler.")
                self._scheduler = rubin_sim.scheduler.example.example_scheduler(nside=self._nside)
                self.logger.info("Finished loading example scheduler.")

    @param.depends(
        "_visits_cds",
        "_almanac_events",
    )
    def airmass_vs_time(self):
        """Create a plot of airmass vs. time.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The bokeh figure.
        """
        if self._visits is None:
            return "No visits loaded"

        if self._almanac_events is None:
            return "Almanac events not computed yet."

        self.logger.info("Starting to update airmass vs. time plot")

        fig = bokeh.plotting.figure(
            title="Airmass",
            x_axis_label="Time (UTC)",
            y_axis_label="Airmass",
            frame_height=512,
            width_policy="max",
            tools="pan,wheel_zoom,box_zoom,box_select,save,reset,help",
        )

        fig = schedview.plot.nightly.plot_airmass_vs_time(
            visits=self._visits_cds, figure=fig, almanac_events=self._almanac_events
        )
        self.logger.info("Finished updating airmass vs. time plot")
        return fig

    @param.depends(
        "_visits_cds",
        "_almanac_events",
    )
    def alt_vs_time(self):
        """Create a plot of altitude vs. time.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The bokeh figure.
        """
        if self._visits_cds is None:
            return "No visits loaded."

        if self._almanac_events is None:
            return "Almanac events not computed yet."

        self.logger.info("Starting to update altitude vs. time plot")

        fig = bokeh.plotting.figure(
            title="Altitude",
            x_axis_label="Time (UTC)",
            y_axis_label="Altitude",
            frame_height=512,
            width_policy="max",
            tools="pan,wheel_zoom,box_zoom,box_select,save,reset,help",
        )

        fig = schedview.plot.nightly.plot_alt_vs_time(
            visits=self._visits_cds, figure=fig, almanac_events=self._almanac_events
        )

        self.logger.info("Finished updating altitude vs. time plot")
        return fig

    @param.depends(
        "_visits_cds",
    )
    def horizon_map(self):
        """Create a polar plot of altitude and azimuth

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The bokeh figure.
        """
        if self._visits_cds is None:
            return "No visits loaded."

        self.logger.info("Starting to update polar alt-az plot")

        fig = bokeh.plotting.figure(
            title="Horizon (Az/Alt) Coordinates",
            x_axis_type=None,
            y_axis_type=None,
            height=512,
            aspect_ratio=1,
            match_aspect=True,
            tools="pan,wheel_zoom,box_zoom,box_select,lasso_select,save,reset,help",
        )

        fig = schedview.plot.nightly.plot_polar_alt_az(visits=self._visits_cds, figure=fig, legend=False)

        self.logger.info("Finished updating polar alt-az plot")
        return fig

    @param.depends(
        "_scheduler",
        "_visits",
    )
    def visit_skymaps(self):
        """Create an interactive skymap of the visits.

        Returns
        -------
        vmap : `bokeh.models.layouts.LayoutDOM`
            The bokeh maps of visits.
        """

        if self._visits is None:
            return "No visits are loaded."

        if self._scheduler is None:
            return "No scheduler is loaded."

        self.logger.info("Starting to update visit skymaps")

        vmap, vmap_data = schedview.plot.visitmap.create_visit_skymaps(
            visits=self._visits,
            scheduler=self._scheduler,
            night_date=self.night,
            timezone=self.timezone,
            observatory=self._observatory,
        )

        if len(vmap_data["visits"]) < 1:
            vmap = "No visits on this night."

        self.logger.info("Finished updating visit skymaps")

        return vmap

    @param.depends("rewards_fname", watch=True)
    def _update_reward_df(self):
        if self.rewards_fname is None or len(self.rewards_fname) < 1:
            return None

        self.logger.info("Starting to update reward dataframe.")

        try:
            reward_df = pd.read_hdf(self.rewards_fname, "reward_df")
            self.logger.info("Finished updating reward dataframe.")
        except Exception as e:
            self.logger.error(e)

        self._reward_df = reward_df

    @param.depends("_reward_df", watch=True)
    def _update_tier_selector(self):
        if self._reward_df is None:
            self.param["tier"].objects = [""]
            self.tier = ""
            return

        self.logger.info("Starting to update tier selector.")
        tiers = self._reward_df.tier_label.unique().tolist()
        self.param["tier"].objects = tiers
        self.tier = tiers[0]
        self.logger.info("Finished updating tier selector.")

    @param.depends("_reward_df", "tier", watch=True)
    def _update_surveys_selector(self):
        init_displayed_surveys = 7

        if self._reward_df is None or self.tier == "":
            self.param["surveys"].objects = [""]
            self.surveys = ""
            return

        self.logger.info("Starting to update surveys selector.")

        surveys = self._reward_df.set_index("tier_label").loc[self.tier, "survey_label"].unique().tolist()
        self.param["surveys"].objects = surveys
        self.surveys = surveys[:init_displayed_surveys] if len(surveys) > init_displayed_surveys else surveys
        self.logger.info("Finished updating surveys selector.")

    @param.depends("_reward_df", "tier", "surveys", watch=True)
    def _update_basis_function_selector(self):
        if self._reward_df is None or self.tier == "" or self.surveys == "":
            self.param["basis_function"].objects = [""]
            self.basis_function = ""
            return

        self.logger.info("Starting to update basis function selector.")

        tier_reward_df = self._reward_df.set_index("tier_label").loc[self.tier, :]

        basis_functions = ["Total"] + (
            tier_reward_df.set_index("survey_label").loc[self.surveys, "basis_function"].unique().tolist()
        )
        self.param["basis_function"].objects = basis_functions
        self.basis_function = "Total"
        self.logger.info("Finished updating basis function selector.")

    @param.depends("rewards_fname", watch=True)
    def _update_obs_rewards(self):
        if self.rewards_fname is None:
            return None

        self.logger.info("Starting to update obs_rewards.")
        try:
            obs_rewards = pd.read_hdf(self.rewards_fname, "obs_rewards")
            self._obs_rewards = obs_rewards
            self.logger.info("Finished updating obs_rewards.")
        except Exception as e:
            self.logger.warning("Could not update obs_rewards.")
            self.logger.error(e)

    @param.depends("_reward_df", "tier")
    def reward_params(self):
        """Create a param set for the reward plot.

        Returns
        -------
        param_set : `panel.Param`
        """
        self.logger.info("Starting to update reward params.")
        if self._reward_df is None:
            this_param_set = pn.Param(
                self.param,
                parameters=["rewards_fname"],
            )
            return this_param_set

        if len(self.param["surveys"].objects) > 10:
            survey_widget = pn.widgets.CrossSelector
        else:
            survey_widget = pn.widgets.MultiSelect

        this_param_set = pn.Param(
            self.param,
            parameters=["rewards_fname", "tier", "basis_function", "surveys"],
            default_layout=pn.Row,
            name="",
            widgets={"surveys": survey_widget},
        )
        self.logger.info("Finished updating reward params.")
        return this_param_set

    @param.depends(
        "_reward_df",
        "tier",
        "_obs_rewards",
        "night",
        "surveys",
        "basis_function",
    )
    def reward_plot(self):
        """Create a plot of the rewards.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The figure with the reward plot.
        """
        if self._reward_df is None:
            return "No rewards are loaded."

        self.logger.info("Starting to update reward plot.")
        fig = schedview.plot.nightbf.plot_rewards(
            reward_df=self._reward_df,
            tier_label=self.tier,
            night=self.night,
            observatory=self._observatory,
            obs_rewards=self._obs_rewards,
            surveys=self.surveys,
            basis_function=self.basis_function,
            plot_kwargs={"height": 256},
        )
        self.logger.info("Finished updating reward plot.")
        return fig

    @param.depends(
        "_reward_df",
        "tier",
        "_obs_rewards",
        "night",
        "surveys",
    )
    def infeasible_plot(self):
        """Create a plot of infeasible basis functions.

        Returns
        -------
        fig : `bokeh.plotting.Figure`
            The figure..
        """
        if self._reward_df is None:
            return "No rewards are loaded."

        self.logger.info("Starting to update infeasible plot.")
        fig = schedview.plot.nightbf.plot_infeasible(
            reward_df=self._reward_df,
            tier_label=self.tier,
            night=self.night,
            observatory=self._observatory,
            surveys=self.surveys,
            plot_kwargs={"height": 256},
        )
        self.logger.info("Finished updating infeasible plot.")
        return fig

    def initialize_tab_contents(self):
        self.logger.info("Starting to create initial dict of tab contents.")
        tab_contents = {
            "Azimuth and altitude": pn.Row(
                pn.param.ParamMethod(self.alt_vs_time, loading_indicator=True),
                pn.param.ParamMethod(self.horizon_map, loading_indicator=True),
            ),
            "Airmass vs. time": pn.param.ParamMethod(self.airmass_vs_time, loading_indicator=True),
            "Sky maps": pn.param.ParamMethod(self.visit_skymaps, loading_indicator=True),
            "Table of visits": pn.param.ParamMethod(self.visit_table, loading_indicator=True),
            "Reward plots": pn.Column(
                pn.param.ParamMethod(self.reward_params, loading_indicator=True),
                pn.param.ParamMethod(self.reward_plot, loading_indicator=True),
                pn.param.ParamMethod(self.infeasible_plot, loading_indicator=True),
            ),
            "Visit explorer": pn.param.ParamMethod(self.visit_explorer, loading_indicator=True),
        }
        self.logger.info("Finished creating initial dict of tab contents.")
        return tab_contents

    @param.depends("_custom_hvplot_tab_settings", "shown_tabs")
    def tab_contents(self):
        self.logger.info("Starting to update tab contents.")
        tab_contents = self.initialize_tab_contents()

        for custom_index, custom_plot in enumerate(self._custom_hvplot_tab_settings):
            tab_contents[custom_plot["name"]] = pn.Column(
                pn.param.ParamMethod(
                    getattr(self, f"custom_hvplot{custom_index}"),
                    loading_indicator=True,
                )
            )

        for tab_name in self.shown_tabs:
            if tab_name not in tab_contents:
                raise ValueError(
                    f"{tab_name} is an unknown tab type. Must be one of {list(tab_contents.keys())}"
                )

        detail_tabs = pn.Tabs(
            *[(tab, tab_contents[tab]) for tab in self.shown_tabs],
            dynamic=False,  # When true, visit_table never renders. Why?
        )

        self.logger.info("Finished updating tab contents.")
        return detail_tabs

    def make_app(
        self,
        night_date=None,
        opsim_db=None,
        scheduler=None,
        rewards=None,
        shown_tabs=None,
        custom_hvplot_tab_settings_file=None,
    ):
        """Create the pre-night briefing app.

        Parameters
        ----------
        night_date : `datetime.date`, optional
            The date of the night to display.
        opsim_db : `str`, optional
            Path to the opsim output database file.
        scheduler : `str`, optional
            Path to the scheduler pickle file.
        rewards : `str`, optional
            Path to the rewards hdf5 file.
        shown_tabs : `list` [`str`], optional
            Names of the tabs to show. If None, show all tabs except the visit
            explorer.
            Default is None.
        custom_hvplot_tab_settings_file : `str`, optional
            The file containing the settings for the custom hvplot tabs.
            Default is None.

        Returns
        -------
        pn_app : `panel.viewable.Viewable`
            or `tuple`
            ['panel.viewable.Viewable', `schedview.prenight.Prenight`]
            The pre-night briefing app.
        """
        if night_date is not None:
            self.night = night_date

        if scheduler is not None:
            self.scheduler_fname = scheduler

        if opsim_db is not None:
            self.opsim_output_fname = opsim_db

        if rewards is not None:
            self.rewards_fname = rewards

        if custom_hvplot_tab_settings_file is not None:
            self.custom_hvplot_tab_settings_file = custom_hvplot_tab_settings_file

        if shown_tabs is not None:
            self.shown_tabs = shown_tabs

        pn_app = pn.Column(
            "<h1>Pre-night briefing</h1>",
            pn.Row(
                pn.Param(
                    self,
                    parameters=[
                        "night",
                        "timezone",
                        "scheduler_fname",
                        "opsim_output_fname",
                    ],
                    name="<h2>Parameters</h2>",
                    widgets={"night": pn.widgets.DatePicker},
                ),
                pn.Column(
                    "<h2>Astronomical Events</h2>",
                    pn.param.ParamMethod(self.almanac_events_table, loading_indicator=True),
                ),
            ),
            pn.param.ParamMethod(self.tab_contents, loading_indicator=True),
            pn.widgets.Debugger(
                name="Debugger",
                level=logging.DEBUG,
                sizing_mode="stretch_both",
                logger_names=["prenight"],
            ),
        ).servable()

        def clear_caches(session_context):
            self.logger.info("session cleared")
            pn_app.stop()

        try:
            pn.state.on_session_destroyed(clear_caches)
        except RuntimeError as e:
            self.logger.info("RuntimeError: %s", e)

        return pn_app


class RestrictedInputPrenight(Prenight):
    """A pre-night dashboard that restricts the data to files in a dir."""

    opsim_output_fname = schedview.param.FileSelectorWithEmptyOption(
        path=f"{PACKAGE_DATA_DIR}/*opsim*.db", label="OpSim output database", default=None, allow_None=True
    )

    scheduler_fname = schedview.param.FileSelectorWithEmptyOption(
        path=f"{PACKAGE_DATA_DIR}/*scheduler*.p*",
        label="Scheduler pickle file",
        default=None,
        allow_None=True,
    )

    rewards_fname = schedview.param.FileSelectorWithEmptyOption(
        path=f"{PACKAGE_DATA_DIR}/*rewards*.h5", label="rewards HDF5 file", default=None, allow_None=True
    )

    def __init__(self, *args, data_dir=None, **kwargs):
        super().__init__(*args, **kwargs)

        if data_dir is not None:
            self.param["opsim_output_fname"].path = f"{data_dir}/*opsim*.db"
            self.param["scheduler_fname"].path = f"{data_dir}/*scheduler*.p*"
            self.param["rewards_fname"].path = f"{data_dir}/*rewards*.h5"


def prenight_app(*args, **kwargs):
    """Create the pre-night briefing app."""

    try:
        data_from_urls = kwargs["data_from_urls"]
        del kwargs["data_from_urls"]
    except KeyError:
        data_from_urls = False

    if data_from_urls:
        prenight = Prenight()
    else:
        try:
            data_dir = kwargs["data_dir"]
        except KeyError:
            data_dir = None

        prenight = RestrictedInputPrenight(data_dir=data_dir)

    try:
        del kwargs["data_dir"]
    except KeyError:
        pass

    app = prenight.make_app(*args, **kwargs)

    return app


def parse_prenight_args():
    """Parse the command line arguments for the pre-night dashboard."""

    parser = argparse.ArgumentParser(description="Pre-night dashboard for Rubin Observatory scheduler.")

    parser.add_argument(
        "--night",
        "-n",
        type=str,
        default=DEFAULT_CURRENT_TIME.datetime.date().strftime("%Y-%m-%d"),
        help="The night to view, in the format YYYY-MM-DD.",
    )

    parser.add_argument(
        "--opsim_db",
        "-o",
        type=str,
        default=None,
        help="The path to the OpSim output database.",
    )

    parser.add_argument(
        "--scheduler",
        "-s",
        type=str,
        default=None,
        help="The path to the scheduler pickle file.",
    )

    parser.add_argument(
        "--rewards",
        "-r",
        type=str,
        default=None,
        help="The path to the rewards HDF5 file.",
    )

    default_data_dir = f"{USDF_DATA_DIR}/*" if os.path.exists(USDF_DATA_DIR) else PACKAGE_DATA_DIR
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
        "--yes",
        action="store_true",
        help="Do not query for confirmation for insecure parameters.",
    )

    parser.add_argument(
        "--shown_tabs",
        "-t",
        type=str,
        nargs="+",
        default=[
            "Azimuth and altitude",
            "Airmass vs. time",
            "Sky maps",
            "Table of visits",
            "Reward plots",
        ],
        help="The names of the tabs to show.",
    )

    parser.add_argument(
        "--custom-hvplot-tab-settings-file",
        "-c",
        type=str,
        default=None,
        help="The file containing the settings for the custom hvplot tabs.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Open a browser window to show the dashboard.",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="The port on which to serve the dashboard.",
    )

    args = parser.parse_args()

    if len(glob(args.data_dir)) == 0 and not args.data_from_urls:
        args.data_dir = PACKAGE_DATA_DIR

    if args.night is not None:
        args.night_date = Time(pd.Timestamp(args.night, tz="UTC")).datetime.date()
        del args.night

    prenight_app_parameters = args.__dict__

    return prenight_app_parameters


def main():
    print("Starting prenight dashboard")

    prenight_app_parameters = parse_prenight_args()

    if not prenight_app_parameters["yes"]:
        if prenight_app_parameters["data_from_urls"]:
            print("You have set the dashboard to allow data to be loaded from arbitrary URLs.")
            print("This is insecure: arbitrary URLs can point to malicious data.")
            print("Do not use this option unless you know what you are doing.")

            response = input("Continue? (y/n) ")
            if response != "y":
                print("Aborting")
                sys.exit(0)

    del prenight_app_parameters["yes"]

    try:
        show = prenight_app_parameters["show"]
        del prenight_app_parameters["show"]
    except KeyError:
        show = False

    prenight_port = prenight_app_parameters["port"]
    del prenight_app_parameters["port"]

    # If the parameter is not set, do not pass it to the app.
    for key in list(prenight_app_parameters):
        if prenight_app_parameters[key] is None:
            del prenight_app_parameters[key]

    def prenight_app_with_params():
        return prenight_app(**prenight_app_parameters)

    pn.serve(
        prenight_app_with_params,
        port=prenight_port,
        title="Prenight Dashboard",
        show=show,
        start=True,
        autoreload=True,
        threaded=True,
        admin=True,
        profiler=True,
    )


if __name__ == "__main__":
    main()
